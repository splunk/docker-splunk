#!/usr/bin/env python
# encoding: utf-8

import os
import re
import time
import pytest
import shlex
import yaml
import docker
import urllib
import requests
import subprocess
import tarfile
import logging
import logging.handlers
import json
import sys
from random import choice
from string import ascii_lowercase
# Code to suppress insecure https warnings
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)


FILE_DIR = os.path.dirname(os.path.realpath(__file__))
FIXTURES_DIR = os.path.join(FILE_DIR, "fixtures")
REPO_DIR = os.path.join(FILE_DIR, "..")
SCENARIOS_DIR = os.path.join(FILE_DIR, "..", "test_scenarios")
EXAMPLE_APP = os.path.join(FIXTURES_DIR, "splunk_app_example")
EXAMPLE_APP_TGZ = os.path.join(FIXTURES_DIR, "splunk_app_example.tgz")
# Setup logging
LOGGER = logging.getLogger("image_test")
LOGGER.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(os.path.join(FILE_DIR, "functional_image_test.log"), maxBytes=25000000)
formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] [%(process)d] %(message)s')
file_handler.setFormatter(formatter)
LOGGER.addHandler(file_handler)

# Docker varaibles
BASE_IMAGE_NAME = "base-debian-9"
SPLUNK_IMAGE_NAME = "splunk-debian-9"
UF_IMAGE_NAME = "splunkforwarder-debian-9"
# Splunk variables
SPLUNK_VERSION = "7.2.3"
SPLUNK_BUILD = "06d57c595b80"
SPLUNK_FILENAME = "splunk-{}-{}-Linux-x86_64.tgz".format(SPLUNK_VERSION, SPLUNK_BUILD)
SPLUNK_BUILD_URL = "https://download.splunk.com/products/splunk/releases/{}/linux/{}".format(SPLUNK_VERSION, SPLUNK_FILENAME)
UF_FILENAME = "splunkforwarder-{}-{}-Linux-x86_64.tgz".format(SPLUNK_VERSION, SPLUNK_BUILD)
UF_BUILD_URL = "https://download.splunk.com/products/universalforwarder/releases/{}/linux/{}".format(SPLUNK_VERSION, UF_FILENAME)
# Ansible version
ANSIBLE_VERSION = "2.7.6"

def generate_random_string():
    return ''.join(choice(ascii_lowercase) for b in range(20))


@pytest.mark.large
class TestDebian9(object):
    """
    Test suite to validate the Splunk Docker image
    """

    logger = LOGGER

    @classmethod
    def setup_class(cls):
        cls.client = docker.APIClient()
        # Setup password
        cls.password = generate_random_string()
        with open(os.path.join(REPO_DIR, ".env"), "w") as f:
            f.write("SPLUNK_PASSWORD={}\n".format(cls.password))
            f.write("SPLUNK_IMAGE={}\n".format(SPLUNK_IMAGE_NAME))
            f.write("UF_IMAGE={}\n".format(UF_IMAGE_NAME))

    @classmethod
    def teardown_class(cls):
        try:
            os.remove(os.path.join(REPO_DIR, ".env"))
        except OSError as e:
            pass
        except Exception as e:
            raise e

    def setup_method(self, method):
        # Make sure all running containers are removed
        self._clean_docker_env()
        self.compose_file_name = None
        self.project_name = None

    def teardown_method(self, method):
        if self.compose_file_name and self.project_name:
            command = "docker-compose -p {} -f test_scenarios/{} down --volumes --remove-orphans".format(self.project_name, self.compose_file_name)
            out, err, rc = self._run_command(command)
            self.compose_file_name, self.project_name = None, None
        self._clean_docker_env()

    def _clean_docker_env(self):
        # Remove anything spun up by docker-compose
        containers = self.client.containers(filters={"label": "com.docker.compose.version"})
        for container in containers:
            self.client.remove_container(container["Id"], v=True, force=True)
        self.client.prune_networks()
        self.client.prune_volumes()

    def _run_command(self, command, cwd=REPO_DIR):
        if isinstance(command, list):
            sh = command
        elif isinstance(command, str):
            sh = shlex.split(command)
        self.logger.info("CALL: %s" % sh)
        proc = subprocess.Popen(sh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        lines = []
        err_lines = []
        for line in iter(proc.stdout.readline, ''):
            lines.append(line)
        for line in iter(proc.stderr.readline, ''):
            err_lines.append(line)
        proc.stdout.close()
        proc.stderr.close()
        proc.wait()
        out = "".join(lines)
        self.logger.info("STDOUT: %s" % out)
        err = "".join(err_lines)
        self.logger.info("STDERR: %s" % err)
        self.logger.info("RC: %s" % proc.returncode)
        return out, err, proc.returncode
    
    def compose_up(self):
        container_count = self.get_number_of_containers(os.path.join(SCENARIOS_DIR, self.compose_file_name))
        command = "docker-compose -p {} -f test_scenarios/{} up -d".format(self.project_name, self.compose_file_name)
        out, err, rc = self._run_command(command)
        return container_count, rc
    
    def get_number_of_containers(self, filename):
        yml = {}
        with open(filename, "r") as f:
            yml = yaml.load(f)
        return len(yml["services"])
    
    def wait_for_containers(self, count, label=None, name=None):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''
        start = time.time()
        end = start
        while end-start < 600:
            filters = {}
            if name:
                filters["name"] = name
            if label:
                filters["label"] = label
            containers = self.client.containers(filters=filters)
            self.logger.info("Found {} containers, expected {}: {}".format(len(containers), count, [x["Names"][0] for x in containers]))
            if len(containers) != count:
                return False
            healthy_count = 0
            for container in containers:
                # The healthcheck on our Splunk image is not reliable - resorting to checking logs
                if container.get("Labels", {}).get("maintainer") == "support@splunk.com":
                    output = self.client.logs(container["Id"], tail=10)
                    if "unable to" in output or "denied" in output or "splunkd.pid file is unreadable" in output:
                        self.logger.error("Container {} did not start properly, last log line: {}".format(container["Names"][0], output))
                    elif "Ansible playbook complete" in output:
                        self.logger.info("Container {} is ready".format(container["Names"][0]))
                        healthy_count += 1
                else:
                    self.logger.info("Container {} is ready".format(container["Names"][0]))
                    healthy_count += 1
            if healthy_count == count:
                self.logger.info("All containers ready to proceed")
                break
            time.sleep(5)
            end = time.time()
        return True
    
    def handle_request_retry(self, method, url, kwargs):
        RETRIES = 6
        IMPLICIT_WAIT = 3
        for n in range(RETRIES):
            try:
                self.logger.info("Attempt #{}: running {} against {} with kwargs {}".format(n+1, method, url, kwargs))
                resp = requests.request(method, url, **kwargs)
                resp.raise_for_status()
                return (resp.status_code, resp.content)
            except Exception as e:
                self.logger.error("Attempt #{} error: {}".format(n+1, str(e)))
                time.sleep(IMPLICIT_WAIT)
                if n < RETRIES-1:
                    continue
                raise e

    def check_splunkd(self, username, password, name=None):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''
        filters = {}
        if name:
            filters["name"] = name
        if self.project_name:
            filters["label"] = "com.docker.compose.project={}".format(self.project_name)
        containers = self.client.containers(filters=filters)
        for container in containers:
            # We can't check splunkd on non-Splunk containers
            if container.get("Labels", {}).get("maintainer") is not "support@splunk.com":
                continue
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": (username, password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        return True

    def get_container_logs(self, container_id):
        stream = self.client.logs(container_id, stream=True)
        output = ""
        for char in stream:
            if "Ansible playbook complete" in char:
                break
            output += char
        return output

    def extract_json(self, container_name):
        retries = 15
        for i in range(retries):
            exec_command = self.client.exec_create(container_name, "cat /opt/container_artifact/ansible_inventory.json")
            json_data = self.client.exec_start(exec_command)
            if "No such file or directory" in json_data:
                time.sleep(5)
            else: 
                break
        try:
            data = json.loads(json_data)
            return data
        except Exception as e:
            self.logger.error(e)
            return None
    
    def search_internal_distinct_hosts(self, container_id, username="admin", password="password"):
        query = "search index=_internal earliest=-1m | stats dc(host) as distinct_hosts"
        splunkd_port = self.client.port(container_id, 8089)[0]["HostPort"]
        url = "https://localhost:{}/services/search/jobs?output_mode=json".format(splunkd_port)
        kwargs = {
                    "auth": (username, password),
                    "data": "search={}".format(urllib.quote_plus(query)),
                    "verify": False
                }
        resp = requests.post(url, **kwargs)
        assert resp.status_code == 201
        sid = json.loads(resp.content)["sid"]
        assert sid
        self.logger.info("Search job {} created against on {}".format(sid, container_id))
        # Wait for search to finish
        # TODO: implement polling mechanism here
        job_status = None
        for _ in range(10):
            url = "https://localhost:{}/services/search/jobs/{}?output_mode=json".format(splunkd_port, sid)
            kwargs = {"auth": (username, password), "verify": False}
            job_status = requests.get(url, **kwargs)
            done = json.loads(job_status.content)["entry"][0]["content"]["isDone"]
            self.logger.info("Search job {} done status is {}".format(sid, done))
            if done:
                break
            time.sleep(3)
        # Check searchProviders - use the latest job_status check from the polling
        assert job_status.status_code == 200
        search_providers = json.loads(job_status.content)["entry"][0]["content"]["searchProviders"]
        assert search_providers
        # Check search results
        url = "https://localhost:{}/services/search/jobs/{}/results?output_mode=json".format(splunkd_port, sid)
        kwargs = {"auth": (username, password), "verify": False}
        resp = requests.get(url, **kwargs)
        assert resp.status_code == 200
        distinct_hosts = int(json.loads(resp.content)["results"][0]["distinct_hosts"])
        assert distinct_hosts
        return search_providers, distinct_hosts
        
    def check_common_keys(self, log_output, role):
        try:
            assert log_output["all"]["vars"]["ansible_ssh_user"] == "splunk"
            assert log_output["all"]["vars"]["ansible_pre_tasks"] == None
            assert log_output["all"]["vars"]["ansible_post_tasks"] == None
            assert log_output["all"]["vars"]["retry_num"] == 50
            assert log_output["all"]["vars"]["delay_num"] == 3
            assert log_output["all"]["vars"]["splunk"]["group"] == "splunk"
            assert log_output["all"]["vars"]["splunk"]["license_download_dest"] == "/tmp/splunk.lic"
            assert log_output["all"]["vars"]["splunk"]["nfr_license"] == "/tmp/nfr_enterprise.lic"
            assert log_output["all"]["vars"]["splunk"]["opt"] == "/opt"
            assert log_output["all"]["vars"]["splunk"]["user"] == "splunk"

            if role == "uf":
                assert log_output["all"]["vars"]["splunk"]["exec"] == "/opt/splunkforwarder/bin/splunk"
                assert log_output["all"]["vars"]["splunk"]["home"] == "/opt/splunkforwarder"
                assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_universal_forwarder"
            else:
                assert log_output["all"]["vars"]["splunk"]["exec"] == "/opt/splunk/bin/splunk"
                assert log_output["all"]["vars"]["splunk"]["home"] == "/opt/splunk"
                if role == "so":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_standalone"
                elif role == "idx":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_indexer"
                elif role == "sh":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_search_head"
                elif role == "cm":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_cluster_master"
        except KeyError as e:
            self.logger.error("{} key not found".format(e))
            assert False

    def check_ansible(self, output):
        assert "ansible-playbook {}".format(ANSIBLE_VERSION) in output
        assert "config file = /opt/ansible/ansible.cfg" in output
    
    def test_splunk_entrypoint_help(self):
        # Run container
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="help")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "SPLUNK_HOME - home directory where Splunk gets installed (default: /opt/splunk)" in output
        assert "Examples:" in output
    
    def test_splunk_entrypoint_create_defaults(self):
        # Run container
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "home: /opt/splunk" in output
        assert "password: " in output
        assert "secret: " in output
    
    def test_splunk_entrypoint_start_no_password(self):
        # Run container
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "WARNING: No password ENV var." in output
    
    def test_splunk_entrypoint_start_no_accept_license(self):
        # Run container
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_PASSWORD": "something", "SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "License not accepted, please ensure the environment variable SPLUNK_START_ARGS contains the '--accept-license' flag" in output
    
    def test_uf_entrypoint_help(self):
        # Run container
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="help")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "DOCKER_MONITORING - 'true or false' - enable docker monitoring" in output
        assert "SPLUNK_CMD - 'any splunk command' - execute any splunk commands separated by commas" in output

    def test_uf_entrypoint_create_defaults(self):
        # Run container
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "home: /opt/splunk" in output
        assert "password: " in output
    
    def test_uf_entrypoint_start_no_password(self):
        # Run container
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "WARNING: No password ENV var." in output
    
    def test_uf_entrypoint_start_no_accept_license(self):
        # Run container
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_PASSWORD": "something", "SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "License not accepted, please ensure the environment variable SPLUNK_START_ARGS contains the '--accept-license' flag" in output
    
    def test_adhoc_1so_using_default_yml(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass
    
    def test_adhoc_1uf_using_default_yml(self):
        # Generate default.yml
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass
    
    def test_adhoc_1so_bind_mount_apps(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/", "/opt/splunk/etc/apps/splunk_app_example/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/", 
                                                                                              EXAMPLE_APP + ":/opt/splunk/etc/apps/splunk_app_example/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check the app endpoint
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Let's go further and check app version
            output = json.loads(content)
            assert output["entry"][0]["content"]["version"] == "0.0.1"
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass
    
    def test_adhoc_1uf_bind_mount_apps(self):
        # Generate default.yml
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/", "/opt/splunkforwarder/etc/apps/splunk_app_example/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/", 
                                                                                              EXAMPLE_APP + ":/opt/splunkforwarder/etc/apps/splunk_app_example/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check the app endpoint
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Let's go further and check app version
            output = json.loads(content)
            assert output["entry"][0]["content"]["version"] == "0.0.1"
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass

    def test_adhoc_1so_hec_ssl_disabled(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Get the HEC token
        hec_token = re.search("  hec_token: (.*)", output).group(1).strip()
        assert hec_token
        # Make sure hec_enableSSL is disabled
        output = re.sub(r'  hec_enableSSL: 1', r'  hec_enableSSL: 0', output)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089, 8088], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check HEC
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "http://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk {}".format(hec_token)}}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass
    
    def test_adhoc_1uf_hec_ssl_disabled(self):
        # Generate default.yml
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Get the HEC token
        hec_token = re.search("  hec_token: (.*)", output).group(1).strip()
        assert hec_token
        # Make sure hec_enableSSL is disabled
        output = re.sub(r'  hec_enableSSL: 1', r'  hec_enableSSL: 0', output)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="start", ports=[8089, 8088], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check HEC
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "http://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk {}".format(hec_token)}}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass

    def test_compose_1so_trial(self):
        # Standup deployment
        self.compose_file_name = "1so_trial.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
    
    def test_compose_1so_custombuild(self):
        # Standup deployment
        self.compose_file_name = "1so_custombuild.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
        
    def test_compose_1so_namedvolumes(self):
        # Standup deployment
        self.compose_file_name = "1so_namedvolumes.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")

    def test_compose_1so_command_start(self):
        # Standup deployment
        self.compose_file_name = "1so_command_start.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
    
    def test_compose_1uf_command_start(self):
        # Standup deployment
        self.compose_file_name = "1uf_command_start.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("uf1")
        output = self.get_container_logs("uf1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "uf")

    def test_compose_1so_command_start_service(self):
        # Standup deployment
        self.compose_file_name = "1so_command_start_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
    
    def test_compose_1uf_command_start_service(self):
        # Standup deployment
        self.compose_file_name = "1uf_command_start_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("uf1")
        output = self.get_container_logs("uf1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "uf")

    def test_compose_1so_java_oracle(self):
        # Standup deployment
        self.compose_file_name = "1so_java_oracle.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "oracle:8"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check if java is installed
        exec_command = self.client.exec_create("so1", "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "java version \"1.8.0" in std_out

    def test_compose_1so_java_openjdk(self):
        # Standup deployment
        self.compose_file_name = "1so_java_openjdk.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "openjdk:8"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check if java is installed
        exec_command = self.client.exec_create("so1", "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"1.8.0" in std_out

    def test_compose_1so_hec(self):
        # Standup deployment
        self.compose_file_name = "1so_hec.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec_token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check HEC works - note the token "abcd1234" is hard-coded within the 1so_hec.yaml compose
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 1
        so1 = containers[0]
        splunk_hec_port = self.client.port(so1["Id"], 8088)[0]["HostPort"]
        url = "https://localhost:{}/services/collector/event".format(splunk_hec_port)
        kwargs = {"json": {"event": "hello world"}, "verify": False, "headers": {"Authorization": "Splunk abcd1234"}}
        status, content = self.handle_request_retry("POST", url, kwargs)
        assert status == 200 

    def test_compose_1so_apps(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1so_apps.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["splunk"]["apps_location"][0] == "http://appserver/splunk_app_example.tgz"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["default"] == "/opt/splunk/etc/apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["deployment"] == "/opt/splunk/etc/deployment-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["httpinput"] == "/opt/splunk/etc/apps/splunk_httpinput"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["idxc"] == "/opt/splunk/etc/master-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["shc"] == "/opt/splunk/etc/shcluster/apps"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check to make sure the app got installed
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 2
        for container in containers:
            # Skip the nginx container
            if "nginx" in container["Image"]:
                continue
            # Check the app endpoint
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Let's go further and check app version
            output = json.loads(content)
            assert output["entry"][0]["content"]["version"] == "0.0.1"
        try:
            os.remove(EXAMPLE_APP_TGZ)
        except OSError as e:
            pass

    def test_compose_1uf_hec(self):
        # Standup deployment
        self.compose_file_name = "1uf_hec.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("uf1")
        output = self.get_container_logs("uf1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "uf")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec_token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check HEC works - note the token "abcd1234" is hard-coded within the 1so_hec.yaml compose
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 1
        uf1 = containers[0]
        splunk_hec_port = self.client.port(uf1["Id"], 8088)[0]["HostPort"]
        url = "https://localhost:{}/services/collector/event".format(splunk_hec_port)
        kwargs = {"json": {"event": "hello world"}, "verify": False, "headers": {"Authorization": "Splunk abcd1234"}}
        status, content = self.handle_request_retry("POST", url, kwargs)
        assert status == 200 

    def test_compose_1uf_apps(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1uf_apps.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        log_json = self.extract_json("uf1")
        output = self.get_container_logs("uf1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "uf")
        try:
            assert log_json["all"]["vars"]["splunk"]["apps_location"][0] == "http://appserver/splunk_app_example.tgz"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["default"] == "/opt/splunkforwarder/etc/apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["deployment"] == "/opt/splunkforwarder/etc/deployment-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["httpinput"] == "/opt/splunkforwarder/etc/apps/splunk_httpinput"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["idxc"] == "/opt/splunkforwarder/etc/master-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["shc"] == "/opt/splunkforwarder/etc/shcluster/apps"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check to make sure the app got installed
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 2
        for container in containers:
            # Skip the nginx container
            if "nginx" in container["Image"]:
                continue
            # Check the app endpoint
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Let's go further and check app version
            output = json.loads(content)
            assert output["entry"][0]["content"]["version"] == "0.0.1"
        try:
            os.remove(EXAMPLE_APP_TGZ)
        except OSError as e:
            pass

    def test_compose_1uf1so(self):
        # Standup deployment
        self.compose_file_name = "1uf1so.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Get container logs
        output_so = self.get_container_logs("so1")
        output_uf = self.get_container_logs("uf1")
        log_json_so = self.extract_json("so1")
        log_json_uf = self.extract_json("uf1")
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output_so)
        self.check_ansible(output_uf)
        # Check values in log output
        self.check_common_keys(log_json_so, "so")
        self.check_common_keys(log_json_uf, "uf")
        try:
            assert log_json_so["splunk_standalone"]["hosts"][0] == "so1"
            assert log_json_uf["splunk_standalone"]["hosts"][0] == "so1"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Search results won't return the correct results immediately :(
        time.sleep(20)
        search_providers, distinct_hosts = self.search_internal_distinct_hosts("so1", password=self.password)
        assert len(search_providers) == 1
        assert search_providers[0] == "so1"
        assert distinct_hosts == 2

    def test_compose_2idx2sh(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"sh1": "sh", "sh2": "sh", "idx1": "idx", "idx2": "idx"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs(container)
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json(container)
            self.check_common_keys(inventory_json, container_mapping[container])
            try:
                assert inventory_json["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
                assert inventory_json["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
            except KeyError as e:
                self.logger.error(e)
                raise e
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Search results won't return the correct results immediately :(
        time.sleep(20)
        search_providers, distinct_hosts = self.search_internal_distinct_hosts("sh1", password=self.password)
        assert len(search_providers) == 3
        assert "idx1" in search_providers and "idx2" in search_providers and "sh1" in search_providers
        assert distinct_hosts == 4
    
    def test_compose_1idx3sh1cm1dep(self):
        # Generate default.yml -- for SHC, we need a common default.yml otherwise things won't work
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Write the default.yml to a file
        with open(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"), "w") as f:
            f.write(output)
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        try:
            self.compose_file_name = "1idx3sh1cm1dep.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to be healthy
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"sh1": "sh", "sh2": "sh", "sh3": "sh", "cm1": "cm", "idx1": "idx", "dep1": "dep"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs(container)
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json(container)
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
                container_name = container["Names"][0].strip("/")
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                if container_name in {"sh1", "sh2", "sh3", "idx1"}:
                    url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
                    kwargs = {"auth": ("admin", self.password), "verify": False}
                    status, content = self.handle_request_retry("GET", url, kwargs)
                    assert status == 200
                # Make sure preferred captain is set
                if container_name == "sh1":
                    url = "https://localhost:{}/servicesNS/nobody/system/configs/conf-server/shclustering?output_mode=json".format(splunkd_port)
                    kwargs = {"auth": ("admin", self.password), "verify": False}
                    status, content = self.handle_request_retry("GET", url, kwargs)
                    assert json.loads(content)["entry"][0]["content"]["preferred_captain"] == "1"
            # Check the app endpoint
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Let's go further and check app version
            assert json.loads(content)["entry"][0]["content"]["version"] == "0.0.1"
            # Search results won't return the correct results immediately :(
            time.sleep(20)
            search_providers, distinct_hosts = self.search_internal_distinct_hosts("sh1", password=self.password)
            assert len(search_providers) == 2
            assert "idx1" in search_providers and "sh1" in search_providers
            assert distinct_hosts == 6
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            try:
                os.remove(EXAMPLE_APP_TGZ)
                os.remove(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"))
            except OSError as e:
                pass