#!/usr/bin/env python
# encoding: utf-8

import pytest
import time
import re
import os
import tarfile
import requests
import tarfile
import docker
import json
import urllib
import yaml
import subprocess
from shutil import copy, copytree, rmtree
from executor import Executor
from docker.types import Mount
# Code to suppress insecure https warnings
import urllib3
from urllib3.exceptions import InsecureRequestWarning, SubjectAltNameWarning
urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(SubjectAltNameWarning)

global PLATFORM
PLATFORM = "debian-9"
OLD_SPLUNK_VERSION = "7.3.4"

def pytest_generate_tests(metafunc):
    # This is called for every test. Only get/set command line arguments
    # if the argument is specified in the list of test "fixturenames".
    option_value = metafunc.config.option.platform
    global PLATFORM
    PLATFORM = option_value

class TestDockerSplunk(Executor):

    @classmethod
    def setup_class(cls):
        super(TestDockerSplunk, cls).setup_class(PLATFORM)

    def setup_method(self, method):
        # Make sure all running containers are removed
        self._clean_docker_env()
        self.compose_file_name = None
        self.project_name = None
        self.DIR = None

    def teardown_method(self, method):
        if self.compose_file_name and self.project_name:
            if self.DIR:
                command = "docker-compose -p {} -f {} down --volumes --remove-orphans".format(self.project_name, os.path.join(self.DIR, self.compose_file_name))
            else:
                command = "docker-compose -p {} -f test_scenarios/{} down --volumes --remove-orphans".format(self.project_name, self.compose_file_name)
            out, err, rc = self._run_command(command)
            self._clean_docker_env()
        if self.DIR:
            try:
                rmtree(self.DIR)
            except OSError:
                pass
        self.compose_file_name, self.project_name, self.DIR = None, None, None

    def test_compose_3idx1cm_custom_repl_factor(self):
        self.project_name = self.generate_random_string()
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Change repl factor & search factor
        output = re.sub(r'    replication_factor: 3', r'''    replication_factor: 2''', output)
        output = re.sub(r'    search_factor: 3', r'''    search_factor: 1''', output)
        # Write the default.yml to a file
        with open(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "3idx1cm.yaml"
            container_count, rc = self.compose_up(defaults_url="/tmp/defaults/{}.yml".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"cm1": "cm", "idx1": "idx", "idx2": "idx", "idx3": "idx"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
                self.check_common_keys(inventory_json, container_mapping[container])
                try:
                    assert inventory_json["splunk_indexer"]["hosts"] == ["idx1", "idx2", "idx3"]
                    assert inventory_json["splunk_cluster_master"]["hosts"] == ["cm1"]
                except KeyError as e:
                    self.logger.error(e)
                    raise e
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed, and shcluster is setup properly
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 4
            for container in containers:
                container_name = container["Names"][0].strip("/").split("_")[1]
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name == "cm1":
                    # Check the replication factor & search factor
                    url = "https://localhost:{}/services/cluster/config/config?output_mode=json".format(splunkd_port)
                    kwargs = {"auth": ("admin", self.password), "verify": False}
                    status, content = self.handle_request_retry("GET", url, kwargs)
                    assert status == 200
                    assert json.loads(content)["entry"][0]["content"]["replication_factor"] == 2
                    assert json.loads(content)["entry"][0]["content"]["search_factor"] == 1
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)))
            except OSError as e:
                pass

    def test_compose_1idx3sh1cm1dep(self):
        self.project_name = self.generate_random_string()
        # Generate default.yml -- for SHC, we need a common default.yml otherwise things won't work
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)), "w") as f:
            f.write(output)
        # Tar the app before spinning up the scenario
        with tarfile.open(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)), "w:gz") as tar:
            tar.add(self.EXAMPLE_APP, arcname=os.path.basename(self.EXAMPLE_APP))
        # Standup deployment
        try:
            self.compose_file_name = "1idx3sh1cm1dep.yaml"
            container_count, rc = self.compose_up(defaults_url="/tmp/defaults/{}.yml".format(self.project_name), apps_url="http://appserver/{}.tgz".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"sh1": "sh", "sh2": "sh", "sh3": "sh", "cm1": "cm", "idx1": "idx", "dep1": "dep"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
                self.check_common_keys(inventory_json, container_mapping[container])
                try:
                    assert inventory_json["splunk_indexer"]["hosts"] == ["idx1"]
                    assert inventory_json["splunk_search_head_captain"]["hosts"] == ["sh1"]
                    assert inventory_json["splunk_search_head"]["hosts"] == ["sh2", "sh3"]
                    assert inventory_json["splunk_cluster_master"]["hosts"] == ["cm1"]
                    assert inventory_json["splunk_deployer"]["hosts"] == ["dep1"]
                except KeyError as e:
                    self.logger.error(e)
                    raise e
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed, and shcluster is setup properly
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 7
            for container in containers:
                # Skip the nginx container
                if "nginx" in container["Image"]:
                    continue
                container_name = container["Names"][0].strip("/").split("_")[1]
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name in {"sh1", "sh2", "sh3", "idx1"}:
                    # Check the app and version
                    url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                    kwargs = {"auth": ("admin", self.password), "verify": False}
                    status, content = self.handle_request_retry("GET", url, kwargs)
                    assert status == 200
                    assert json.loads(content)["entry"][0]["content"]["version"] == "0.0.1"
                # Make sure preferred captain is set
                if container_name == "sh1":
                    url = "https://localhost:{}/servicesNS/nobody/system/configs/conf-server/shclustering?output_mode=json".format(splunkd_port)
                    kwargs = {"auth": ("admin", self.password), "verify": False}
                    status, content = self.handle_request_retry("GET", url, kwargs)
                    assert json.loads(content)["entry"][0]["content"]["preferred_captain"] == "1"
            # Search results won't return the correct results immediately :(
            time.sleep(30)
            RETRIES = 10
            IMPLICIT_WAIT = 6
            for n in range(RETRIES):
                try:
                    self.logger.info("Attempt #{}: checking internal search host count".format(n+1))
                    search_providers, distinct_hosts = self.search_internal_distinct_hosts("{}_sh1_1".format(self.project_name), password=self.password)
                    assert len(search_providers) == 2
                    assert "idx1" in search_providers and "sh1" in search_providers
                    assert distinct_hosts == 6
                    break
                except Exception as e:
                    self.logger.error("Attempt #{} error: {}".format(n+1, str(e)))
                    if n < RETRIES-1:
                        time.sleep(IMPLICIT_WAIT)
                        continue
                    raise e
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)))
                os.remove(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)))
            except OSError as e:
                pass

    def test_compose_1uf1so(self):
        # Standup deployment
        self.compose_file_name = "1uf1so.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"so1": "so", "uf1": "uf"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
            self.check_common_keys(inventory_json, container_mapping[container])
            try:
                assert inventory_json["splunk_standalone"]["hosts"] == ["so1"]
            except KeyError as e:
                self.logger.error(e)
                raise e
        # Search results won't return the correct results immediately :(
        time.sleep(30)
        search_providers, distinct_hosts = self.search_internal_distinct_hosts("{}_so1_1".format(self.project_name), password=self.password)
        assert len(search_providers) == 1
        assert search_providers[0] == "so1"
        assert distinct_hosts == 2
 
    def test_compose_3idx1cm_default_repl_factor(self):
        self.project_name = self.generate_random_string()
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "3idx1cm.yaml"
            container_count, rc = self.compose_up(defaults_url="/tmp/defaults/{}.yml".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"cm1": "cm", "idx1": "idx", "idx2": "idx", "idx3": "idx"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
                self.check_common_keys(inventory_json, container_mapping[container])
                try:
                    assert inventory_json["splunk_indexer"]["hosts"] == ["idx1", "idx2", "idx3"]
                    assert inventory_json["splunk_cluster_master"]["hosts"] == ["cm1"]
                except KeyError as e:
                    self.logger.error(e)
                    raise e
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed, and shcluster is setup properly
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 4
            for container in containers:
                container_name = container["Names"][0].strip("/").split("_")[1]
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name == "cm1":
                    # Check the replication factor & search factor
                    url = "https://localhost:{}/services/cluster/config/config?output_mode=json".format(splunkd_port)
                    kwargs = {"auth": ("admin", self.password), "verify": False}
                    status, content = self.handle_request_retry("GET", url, kwargs)
                    assert status == 200
                    assert json.loads(content)["entry"][0]["content"]["replication_factor"] == 3
                    assert json.loads(content)["entry"][0]["content"]["search_factor"] == 3
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)))
            except OSError as e:
                pass

    def test_compose_1so1cm_connected(self):
        # Standup deployment
        self.compose_file_name = "1so1cm_connected.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"so1": "so", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
            self.check_common_keys(inventory_json, container_mapping[container])
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            container_name = container["Names"][0].strip("/").split('_')[1]
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            if container_name == "cm1":
                status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/searchheads?output_mode=json".format(splunkd_port), 
                    {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                assert len(output["entry"]) == 2
                for sh in output["entry"]:
                    assert sh["content"]["label"] in ["cm1", "so1"]
                    assert sh["content"]["status"] == "Connected"

    def test_compose_1so1cm_unconnected(self):
        # Standup deployment
        self.compose_file_name = "1so1cm_unconnected.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"so1": "so", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
            self.check_common_keys(inventory_json, container_mapping[container])
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            container_name = container["Names"][0].strip("/").split('_')[1]
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            if container_name == "cm1":
                status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/searchheads?output_mode=json".format(splunkd_port), 
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                assert len(output["entry"]) == 1
                assert output["entry"][0]["content"]["label"] == "cm1"
                assert output["entry"][0]["content"]["status"] == "Connected"

    def test_adhoc_1cm_idxc_pass4symmkey(self):
        # Create the container
        cid = None
        try:
            self.project_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=self.project_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ROLE": "splunk_cluster_master",
                                                            "SPLUNK_INDEXER_URL": "idx1",
                                                            "SPLUNK_IDXC_PASS4SYMMKEY": "keepsummerbeingliketotallystokedaboutlikethegeneralvibeandstuff",
                                                            "SPLUNK_IDXC_LABEL": "keepsummersafe",
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=self.project_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check if the cluster label and pass4SymmKey line up
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "cluster_label = keepsummersafe" in std_out
            pass4SymmKey = re.search(r'\[clustering\].*?pass4SymmKey = (.*?)\n', std_out, flags=re.MULTILINE|re.DOTALL).group(1).strip()
            exec_command = self.client.exec_create(cid, "/opt/splunk/bin/splunk show-decrypted --value '{}'".format(pass4SymmKey), user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "keepsummerbeingliketotallystokedaboutlikethegeneralvibeandstuff" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_compose_1cm_smartstore(self):
        # Generate default.yml
        self.project_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, self.project_name)
        os.mkdir(self.DIR)
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Add a custom conf file
        output = re.sub(r'  smartstore: null', r'''  smartstore:
    index:
        - indexName: default
          remoteName: remote_vol
          scheme: s3
          remoteLocation: smartstore-test
          s3:
            access_key: abcd
            secret_key: 1234
            endpoint: https://s3-region.amazonaws.com''', output)
        # Write the default.yml to a file
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/tmp/defaults/default.yml"], name=self.project_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ROLE": "splunk_cluster_master",
                                                            "SPLUNK_INDEXER_URL": "idx1"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.DIR + "/default.yml:/tmp/defaults/default.yml"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=self.project_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/master-apps/_cluster/local/indexes.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert 'remotePath = volume:remote_vol/$_index_name' in std_out
            assert 'repFactor = auto' in std_out
            assert '[volume:remote_vol]' in std_out
            assert 'storageType = remote' in std_out
            assert 'path = s3://smartstore-test' in std_out
            assert 'remote.s3.access_key = abcd' in std_out
            assert 'remote.s3.secret_key = 1234' in std_out
            assert 'remote.s3.endpoint = https://s3-region.amazonaws.com' in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(self.DIR, "default.yml"))
            except OSError:
                pass

    def test_compose_1sh1cm(self):
        # Standup deployment
        self.compose_file_name = "1sh1cm.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"sh1": "sh", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
            self.check_common_keys(inventory_json, container_mapping[container])
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            container_name = container["Names"][0].strip("/").split('_')[1]
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            if container_name == "cm1":
                status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/searchheads?output_mode=json".format(splunkd_port), 
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                # There's only 1 "standalone" search head connected and 1 cluster master
                assert len(output["entry"]) == 2
                for sh in output["entry"]:
                    assert sh["content"]["label"] == "sh1" or sh["content"]["label"] == "cm1"
                    assert sh["content"]["status"] == "Connected"

    def test_compose_1sh1cm1dmc(self):
        # Standup deployment
        self.compose_file_name = "1sh1cm1dmc.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.check_dmc(containers, 2, 0, 2, 1, 3)

    def test_compose_1sh2idx2hf1dmc(self):
        # Standup deployment
        self.compose_file_name = "1sh2idx2hf1dmc.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.check_dmc(containers, 3, 2, 2, 0, 4)

    def test_compose_3idx1cm1dmc(self):
        # Standup deployment
        self.compose_file_name = "3idx1cm1dmc.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=900)
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.check_dmc(containers, 4, 3, 2, 1, 5)

    def test_compose_1uf1so1dmc(self):
        # Standup deployment
        self.compose_file_name = "1uf1so1dmc.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.check_dmc(containers, 1, 1, 1, 0, 2)

    def test_compose_1so1dmc(self):
        # Standup deployment
        self.compose_file_name = "1so1dmc.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.check_dmc(containers, 1, 1, 1, 0, 2)

    def test_compose_2idx2sh1dmc(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh1dmc.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.check_dmc(containers, 4, 2, 3, 0, 5)

    def test_compose_2idx2sh(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"sh1": "sh", "sh2": "sh", "idx1": "idx", "idx2": "idx"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
            self.check_common_keys(inventory_json, container_mapping[container])
            try:
                assert inventory_json["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
                assert inventory_json["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
            except KeyError as e:
                self.logger.error(e)
                raise e
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        idx_list = ["idx1", "idx2"]
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            c_name = container["Labels"]["com.docker.compose.service"]
            if "sh1" in c_name or "sh2" in c_name:
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                url = "https://localhost:{}/services/search/distributed/peers?output_mode=json".format(splunkd_port)
                kwargs = {"auth": ("admin", self.password), "verify": False}
                status, content = self.handle_request_retry("GET", url, kwargs)
                assert status == 200
                output = json.loads(content)
                peers = [x["content"]["peerName"] for x in output["entry"]]
                assert len(peers) == 2 and set(peers) == set(idx_list)
        # Search results won't return the correct results immediately :(
        time.sleep(30)
        search_providers, distinct_hosts = self.search_internal_distinct_hosts("{}_sh1_1".format(self.project_name), password=self.password)
        assert len(search_providers) == 3
        assert "idx1" in search_providers and "idx2" in search_providers and "sh1" in search_providers
        assert distinct_hosts == 4

    def test_compose_2idx2sh1cm(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh1cm.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
        # Get container logs
        container_mapping = {"sh1": "sh", "sh2": "sh", "idx1": "idx", "idx2": "idx", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
            self.check_common_keys(inventory_json, container_mapping[container])
            try:
                assert inventory_json["splunk_cluster_master"]["hosts"] == ["cm1"]
                assert inventory_json["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
                assert inventory_json["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
            except KeyError as e:
                self.logger.error(e)
                raise e
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        idx_list = ["idx1", "idx2"]
        sh_list = ["sh1", "sh2", "cm1"]

        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            container_name = container["Names"][0].strip("/").split('_')[1]
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            if container_name == "cm1":
                status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/searchheads?output_mode=json".format(splunkd_port), 
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                for sh in output["entry"]:
                    if sh["content"]["label"] in sh_list and sh["content"]["status"] == "Connected":
                        sh_list.remove(sh["content"]["label"])
                status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/peers?output_mode=json".format(splunkd_port), 
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                for idx in output["entry"]:
                    if idx["content"]["label"] in idx_list and idx["content"]["status"] == "Up":
                        idx_list.remove(idx["content"]["label"])
                assert len(idx_list) == 0 and len(sh_list) == 0
                # Add one more indexer
                self.compose_file_name = "2idx2sh1cm_idx3.yaml"
                _, rc = self.compose_up()
                assert rc == 0
                # Wait for containers to come up
                assert self.wait_for_containers(container_count+1, label="com.docker.compose.project={}".format(self.project_name), timeout=600)

                retries = 10
                for n in range(retries):
                    try:
                        status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/peers?output_mode=json".format(splunkd_port), 
                                                        {"auth": ("admin", self.password), "verify": False})
                        assert status == 200
                        output = json.loads(content)
                        assert len(output["entry"]) == 3
                        indexers = []
                        for idx in output["entry"]:
                            indexers.append(idx["content"]["label"])
                        assert "idx1" in indexers
                        assert "idx2" in indexers
                        assert "idx3" in indexers
                        break
                    except Exception as err:
                        time.sleep(10)
                        if n < retries-1:
                            continue
                        raise err

    def test_compose_1deployment1cm(self):
        self.project_name = self.generate_random_string()
        # Tar the app before spinning up the scenario
        with tarfile.open(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)), "w:gz") as tar:
            tar.add(self.EXAMPLE_APP, arcname=os.path.basename(self.EXAMPLE_APP))
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Add a custom conf file
        output = re.sub(r'  group: splunk', r'''  group: splunk
  conf:
    - key: user-prefs
      value:
        directory: /opt/splunk/etc/users/admin/user-prefs/local
        content:
          general:
            default_namespace: appboilerplate
            search_syntax_highlighting: dark
            search_assistant:
          "serverClass:secrets:app:test": {}''', output)
        # Write the default.yml to a file
        with open(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "1deployment1cm.yaml"
            container_count, rc = self.compose_up(defaults_url="/tmp/defaults/{}.yml".format(self.project_name), apps_url="http://appserver/{}.tgz".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"cm1": "cm", "depserver1": "deployment_server"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
                self.check_common_keys(inventory_json, container_mapping[container])
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed and certain subdirectories are excluded
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 3
            for container in containers:
                # Skip the nginx container
                if "nginx" in container["Image"]:
                    continue
                container_name = container["Names"][0].strip("/").split("_")[1]
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name == "depserver1":
                    # Check the app and version
                    url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                    resp = requests.get(url, auth=("admin", self.password), verify=False)
                    # Deployment server should *not* install the app
                    assert resp.status_code == 404
                    # Check that the app exists in etc/apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" in std_out
                    assert "app.conf" in std_out
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/apps/splunk_app_example/local/app.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "state = disabled" in std_out
                    # Check that the app exists in etc/deployment-apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/deployment-apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" in std_out
                    assert "app.conf" in std_out
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/deployment-apps/splunk_app_example/local/app.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "# Autogenerated file " == std_out
                if container_name == "cm1":
                    # Check if the created file exists
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/users/admin/user-prefs/local/user-prefs.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "[serverClass:secrets:app:test]" in std_out
                    assert "[general]" in std_out
                    assert "default_namespace = appboilerplate" in std_out
                    assert "search_syntax_highlighting = dark" in std_out
                    assert "search_assistant" in std_out
                    RETRIES = 5
                    for i in range(RETRIES):
                        try:
                            # Check the app and version
                            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                            kwargs = {"auth": ("admin", self.password), "verify": False}
                            status, content = self.handle_request_retry("GET", url, kwargs)
                            assert status == 200
                            assert json.loads(content)["entry"][0]["content"]["version"] == "0.0.1"
                            exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/apps/splunk_app_example/local/", user="splunk")
                            std_out = self.client.exec_start(exec_command)
                            assert "savedsearches.conf" in std_out
                            assert "app.conf" in std_out
                            exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/apps/splunk_app_example/local/app.conf", user="splunk")
                            std_out = self.client.exec_start(exec_command)
                            assert "# Autogenerated file" in std_out
                            assert "state = enabled" in std_out
                        except Exception as e:
                            self.logger.error(e)
                            if i < RETRIES-1:
                                time.sleep(30)
                                continue
                            raise e
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(os.path.join(self.SCENARIOS_DIR, "defaults", "{}.yml".format(self.project_name)))
                os.remove(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)))
            except OSError as e:
                pass

    def test_compose_1deployment1so(self):
        self.project_name = self.generate_random_string()
        # Tar the app before spinning up the scenario
        with tarfile.open(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)), "w:gz") as tar:
            tar.add(self.EXAMPLE_APP, arcname=os.path.basename(self.EXAMPLE_APP))
        # Standup deployment
        try:
            self.compose_file_name = "1deployment1so.yaml"
            container_count, rc = self.compose_up(apps_url="http://appserver/{}.tgz".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"{}_so1_1".format(self.project_name): "so", "{}_depserver1_1".format(self.project_name): "deployment_server"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs(container)
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json(container)
                self.check_common_keys(inventory_json, container_mapping[container])
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed and certain subdirectories are excluded
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 3
            for container in containers:
                # Skip the nginx container
                if "nginx" in container["Image"]:
                    continue
                container_name = container["Names"][0].strip("/").split('_')[1]
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name == "depserver1":
                    # Check the app and version
                    url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                    resp = requests.get(url, auth=("admin", self.password), verify=False)
                    # Deployment server should *not* install the app
                    assert resp.status_code == 404
                    # Check that the app exists in etc/apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" in std_out
                    assert "app.conf" in std_out
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/apps/splunk_app_example/local/app.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "state = disabled" in std_out
                    # Check that the app exists in etc/deployment-apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/deployment-apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" in std_out
                    assert "app.conf" in std_out
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/deployment-apps/splunk_app_example/local/app.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "# Autogenerated file " == std_out
                if container_name == "so1":
                    RETRIES = 5
                    for i in range(RETRIES):
                        try:
                            # Check the app and version
                            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                            kwargs = {"auth": ("admin", self.password), "verify": False}
                            status, content = self.handle_request_retry("GET", url, kwargs)
                            assert status == 200
                            assert json.loads(content)["entry"][0]["content"]["version"] == "0.0.1"
                            exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/apps/splunk_app_example/local/", user="splunk")
                            std_out = self.client.exec_start(exec_command)
                            assert "savedsearches.conf" in std_out
                            assert "app.conf" in std_out
                            exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/apps/splunk_app_example/local/app.conf", user="splunk")
                            std_out = self.client.exec_start(exec_command)
                            assert "# Autogenerated file" in std_out
                            assert "state = enabled" in std_out
                        except Exception as e:
                            self.logger.error(e)
                            if i < RETRIES-1:
                                time.sleep(30)
                                continue
                            raise e
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)))
            except OSError:
                pass

    def test_compose_1deployment1uf(self):
        self.project_name = self.generate_random_string()
        # Tar the app before spinning up the scenario
        with tarfile.open(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)), "w:gz") as tar:
            tar.add(self.EXAMPLE_APP, arcname=os.path.basename(self.EXAMPLE_APP))
        # Standup deployment
        try:
            self.compose_file_name = "1deployment1uf.yaml"
            container_count, rc = self.compose_up(apps_url="http://appserver/{}.tgz".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"{}_uf1_1".format(self.project_name): "uf", "{}_depserver1_1".format(self.project_name): "deployment_server"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs(container)
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json(container)
                self.check_common_keys(inventory_json, container_mapping[container])
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed, and shcluster is setup properly
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 3
            for container in containers:
                # Skip the nginx container
                if "nginx" in container["Image"]:
                    continue
                container_name = container["Names"][0].strip("/")
                container_name = container_name.split('_')[1]
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name == "depserver1":
                    # Check the app and version
                    url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                    resp = requests.get(url, auth=("admin", self.password), verify=False)
                    # Deployment server should *not* install the app
                    assert resp.status_code == 404
                    # Check that the app exists in etc/apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" in std_out
                    assert "app.conf" in std_out
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/apps/splunk_app_example/local/app.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "state = disabled" in std_out
                    # Check that the app exists in etc/deployment-apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/deployment-apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" in std_out
                    assert "app.conf" in std_out
                    exec_command = self.client.exec_create(container["Id"], "cat /opt/splunk/etc/deployment-apps/splunk_app_example/local/app.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "# Autogenerated file " == std_out
                if container_name == "uf1":
                    RETRIES = 5
                    for i in range(RETRIES):
                        try:
                            # Check the app and version
                            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                            kwargs = {"auth": ("admin", self.password), "verify": False}
                            status, content = self.handle_request_retry("GET", url, kwargs)
                            assert status == 200
                            assert json.loads(content)["entry"][0]["content"]["version"] == "0.0.1"
                            exec_command = self.client.exec_create(container["Id"], "ls /opt/splunkforwarder/etc/apps/splunk_app_example/local/", user="splunk")
                            std_out = self.client.exec_start(exec_command)
                            assert "savedsearches.conf" in std_out
                            assert "app.conf" in std_out
                            exec_command = self.client.exec_create(container["Id"], "cat /opt/splunkforwarder/etc/apps/splunk_app_example/local/app.conf", user="splunk")
                            std_out = self.client.exec_start(exec_command)
                            assert "# Autogenerated file" in std_out
                            assert "state = enabled" in std_out
                        except Exception as e:
                            self.logger.error(e)
                            if i < RETRIES-1:
                                time.sleep(30)
                                continue
                            raise e
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)))
            except OSError:
                pass

    def test_compose_3idx1cm_splunktcp_ssl(self):
        self.project_name = self.generate_random_string()
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "carolebaskindidit"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DEFAULTS_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DEFAULTS_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DEFAULTS_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DEFAULTS_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DEFAULTS_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DEFAULTS_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DEFAULTS_DIR)
            ]
        for cmd in cmds:
            execute_cmd = subprocess.check_output(["/bin/sh", "-c", cmd])
        # Update s2s ssl settings
        output = re.sub(r'''  s2s:.*?ssl: false''', r'''  s2s:
    ca: /tmp/defaults/ca.pem
    cert: /tmp/defaults/cert.pem
    enable: true
    password: {}
    port: 9997
    ssl: true'''.format(passphrase), output, flags=re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(self.DEFAULTS_DIR, "{}.yml".format(self.project_name)), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "3idx1cm.yaml"
            container_count, rc = self.compose_up(defaults_url="/tmp/defaults/{}.yml".format(self.project_name))
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"cm1": "cm", "idx1": "idx", "idx2": "idx", "idx3": "idx"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs("{}_{}_1".format(self.project_name, container))
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json("{}_{}_1".format(self.project_name, container))
                self.check_common_keys(inventory_json, container_mapping[container])
                try:
                    assert inventory_json["splunk_indexer"]["hosts"] == ["idx1", "idx2", "idx3"]
                    assert inventory_json["splunk_cluster_master"]["hosts"] == ["cm1"]
                except KeyError as e:
                    self.logger.error(e)
                    raise e
            # Check Splunkd on all the containers
            assert self.check_splunkd("admin", self.password)
            # Make sure apps are installed, and shcluster is setup properly
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 4
            for container in containers:
                container_name = container["Names"][0].strip("/").split("_")[1]
                cid = container["Id"]
                exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/inputs.conf", user="splunk")
                std_out = self.client.exec_start(exec_command)
                assert "[splunktcp-ssl:9997]" in std_out
                assert "disabled = 0" in std_out
                assert "[SSL]" in std_out
                assert "serverCert = /tmp/defaults/cert.pem" in std_out
                assert "[sslConfig]" not in std_out
                assert "rootCA = /tmp/defaults/ca.pem" in std_out
                if container_name == "cm1":
                    exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/outputs.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "clientCert = /tmp/defaults/cert.pem" in std_out
                    assert "sslPassword" in std_out
                    assert "useClientSSLCompression = true" in std_out
                    # Check that data is being forwarded properly
                    time.sleep(30)
                    search_providers, distinct_hosts = self.search_internal_distinct_hosts("{}_cm1_1".format(self.project_name), password=self.password)
                    assert len(search_providers) == 4
                    assert "idx1" in search_providers
                    assert "idx2" in search_providers
                    assert "idx3" in search_providers
                    assert distinct_hosts == 4
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            files = [
                        os.path.join(self.DEFAULTS_DIR, "ca.key"),
                        os.path.join(self.DEFAULTS_DIR, "ca.csr"),
                        os.path.join(self.DEFAULTS_DIR, "ca.pem"),
                        os.path.join(self.DEFAULTS_DIR, "server.key"),
                        os.path.join(self.DEFAULTS_DIR, "server.csr"),
                        os.path.join(self.DEFAULTS_DIR, "server.pem"),
                        os.path.join(self.DEFAULTS_DIR, "cert.pem"),
                        os.path.join(self.DEFAULTS_DIR, "{}.yml".format(self.project_name))
                    ]
            self.cleanup_files(files)