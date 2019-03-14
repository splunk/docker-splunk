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
SPLUNK_VERSION = "7.2.5"
SPLUNK_BUILD = "088f49762779"
SPLUNK_FILENAME = "splunk-{}-{}-Linux-x86_64.tgz".format(SPLUNK_VERSION, SPLUNK_BUILD)
SPLUNK_BUILD_URL = "https://download.splunk.com/products/splunk/releases/{}/linux/{}".format(SPLUNK_VERSION, SPLUNK_FILENAME)
UF_FILENAME = "splunkforwarder-{}-{}-Linux-x86_64.tgz".format(SPLUNK_VERSION, SPLUNK_BUILD)
UF_BUILD_URL = "https://download.splunk.com/products/universalforwarder/releases/{}/linux/{}".format(SPLUNK_VERSION, UF_FILENAME)


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
        while end-start < 300:
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
                if n < RETRIES-1:
                    time.sleep(IMPLICIT_WAIT)
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
            if "maintainer" not in container["Labels"] or container["Labels"]["maintainer"] != "support@splunk.com":
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
                elif role == "deployment_server":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_deployment_server"
                elif role == "idx":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_indexer"
                elif role == "sh":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_search_head"
                elif role == "hf":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_heavy_forwarder"
                elif role == "cm":
                    assert log_output["all"]["vars"]["splunk"]["role"] == "splunk_cluster_master"
        except KeyError as e:
            self.logger.error("{} key not found".format(e))
            assert False

    def check_ansible(self, output):
        assert "ansible-playbook" in output
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

    def test_splunk_entrypoint_no_provision(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "cat /opt/ansible/version.txt")
            std_out = self.client.exec_start(exec_command)
            assert len(std_out.strip()) == 40
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_uf_entrypoint_help(self):
        # Run container
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="help")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
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

    def test_uf_entrypoint_no_provision(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "cat /opt/ansible/version.txt")
            std_out = self.client.exec_start(exec_command)
            assert len(std_out.strip()) == 40
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_adhoc_1so_using_default_yml(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Change the admin user
        output = re.sub(r'  admin_user: admin', r'  admin_user: chewbacca', output)
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
            kwargs = {"auth": ("chewbacca", password), "verify": False}
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
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Change the admin user
        output = re.sub(r'  admin_user: admin', r'  admin_user: hansolo', output)
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
            kwargs = {"auth": ("hansolo", password), "verify": False}
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

    def test_adhoc_1so_custom_conf(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Add a custom conf file
        output = re.sub(r'  group: splunk', r'''  group: splunk
  conf:
    user-prefs:
      directory: /opt/splunk/etc/users/admin/user-prefs/local
      content:
        general:
          default_namespace: appboilerplate
          search_syntax_highlighting: dark''', output)
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
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/users/admin/user-prefs/local/user-prefs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[general]" in std_out
            assert "default_namespace = appboilerplate" in std_out
            assert "search_syntax_highlighting = dark" in std_out
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
    
    def test_adhoc_1uf_custom_conf(self):
        # Generate default.yml
        cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Add a custom conf file
        output = re.sub(r'  group: splunk', r'''  group: splunk
  conf:
    user-prefs:
      directory: /opt/splunkforwarder/etc/users/admin/user-prefs/local
      content:
        general:
          default_namespace: appboilerplate
          search_syntax_highlighting: dark''', output)
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
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/users/admin/user-prefs/local/user-prefs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[general]" in std_out
            assert "default_namespace = appboilerplate" in std_out
            assert "search_syntax_highlighting = dark" in std_out
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

    def test_adhoc_1so_preplaybook(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_PRE_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/touch_dummy_file.yml:/playbooks/play.yml"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /tmp/i-am", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "batman" in std_out
            # Check file owner
            exec_command = self.client.exec_create(cid, r'stat -c \'%U\' /tmp/i-am')
            std_out = self.client.exec_start(exec_command)
            assert "splunk" in std_out
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

    def test_adhoc_1so_preplaybook_with_sudo(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_PRE_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/sudo_touch_dummy_file.yml:/playbooks/play.yml"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /tmp/i-am", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "batman" in std_out
            # Check file owner
            exec_command = self.client.exec_create(cid, r'stat -c \'%U\' /tmp/i-am')
            std_out = self.client.exec_start(exec_command)
            assert "root" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_postplaybook(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_POST_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/touch_dummy_file.yml:/playbooks/play.yml"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /tmp/i-am", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "batman" in std_out
            # Check file owner
            exec_command = self.client.exec_create(cid, r'stat -c \'%U\' /tmp/i-am')
            std_out = self.client.exec_start(exec_command)
            assert "splunk" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_postplaybook_with_sudo(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_POST_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/sudo_touch_dummy_file.yml:/playbooks/play.yml"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", self.password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /tmp/i-am", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "batman" in std_out
            # Check file owner
            exec_command = self.client.exec_create(cid, r'stat -c \'%U\' /tmp/i-am')
            std_out = self.client.exec_start(exec_command)
            assert "root" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_bind_mount_apps(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
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
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
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
        # Get the password
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
            cid = self.client.create_container(UF_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
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
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8089, 8088], 
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
            cid = self.client.create_container(UF_IMAGE_NAME, tty=True, ports=[8089, 8088], 
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

    def test_adhoc_1so_web_ssl(self):
        # Generate a password
        password = generate_random_string()
        # Create the container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            # Commands to generate self-signed certificates for SplunkWeb here: https://docs.splunk.com/Documentation/Splunk/latest/Security/Self-signcertificatesforSplunkWeb
            cmd = "openssl req -x509 -newkey rsa:4096 -passout pass:abcd1234 -keyout {path}/key.pem -out {path}/cert.pem -days 365 -subj /CN=localhost".format(path=FIXTURES_DIR)
            generate_certs = subprocess.check_output(cmd.split())
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password,
                                                            "SPLUNK_HTTP_ENABLESSL": "true",
                                                            "SPLUNK_HTTP_ENABLESSL_CERT": "/tmp/defaults/cert.pem",
                                                            "SPLUNK_HTTP_ENABLESSL_PRIVKEY": "/tmp/defaults/key.pem",
                                                            "SPLUNK_HTTP_ENABLESSL_PRIVKEY_PASSWORD": "abcd1234"
                                                            },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check splunkweb
            web_port = self.client.port(cid, 8000)[0]["HostPort"]
            url = "https://localhost:{}/".format(web_port)
            kwargs = {"verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(FIXTURES_DIR, "key.pem"))
                os.remove(os.path.join(FIXTURES_DIR, "cert.pem"))
            except OSError:
                pass

    def test_compose_1so_trial(self):
        # Standup deployment
        self.compose_file_name = "1so_trial.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
    
    def test_compose_1so_custombuild(self):
        # Standup deployment
        self.compose_file_name = "1so_custombuild.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        
    def test_compose_1so_namedvolumes(self):
        # TODO: We can do a lot better in this test - ex. check that data is persisted after restarts
        # Standup deployment
        self.compose_file_name = "1so_namedvolumes.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)

    def test_compose_1deployment1so(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        try:
            self.compose_file_name = "1deployment1so.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"so1": "so", "depserver1": "deployment_server"}
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
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
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
                os.remove(EXAMPLE_APP_TGZ)
            except OSError as e:
                pass

    def test_compose_1so_before_start_cmd(self):
        # Check that SPLUNK_BEFORE_START_CMD works for splunk image
        # Standup deployment
        self.compose_file_name = "1so_before_start_cmd.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("admin2", "changemepls")
        assert self.check_splunkd("admin3", "changemepls")

    def test_compose_1uf_before_start_cmd(self):
        # Check that SPLUNK_BEFORE_START_CMD works for splunkforwarder image
        # Standup deployment
        self.compose_file_name = "1uf_before_start_cmd.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("normalplebe", "newpassword")
    
    def test_compose_1so_splunk_add(self):
        # Check that SPLUNK_ADD works for splunk image (role=standalone)
        # Standup deployment
        self.compose_file_name = "1so_splunk_add_user.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("newman", "changemepls")
    
    def test_compose_1hf_splunk_add(self):
        # Check that SPLUNK_ADD works for splunk image (role=heavy forwarder)
        # Standup deployment
        self.compose_file_name = "1hf_splunk_add_user.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("hf1")
        self.check_common_keys(log_json, "hf")
        # Check container logs
        output = self.get_container_logs("hf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("jerry", "seinfeld")
    
    def test_compose_1uf_splunk_add(self):
        # Check that SPLUNK_ADD works for splunkforwarder image
        # Standup deployment
        self.compose_file_name = "1uf_splunk_add_user.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("elaine", "changemepls")
        assert self.check_splunkd("kramer", "changemepls")

    def test_compose_1uf_splunk_cmd(self):
        # Check that SPLUNK_ADD works for splunkforwarder image
        # Standup deployment
        self.compose_file_name = "1uf_splunk_cmd.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("jerry", "changemepls")
        assert self.check_splunkd("george", "changemepls")

    @pytest.mark.skip(reason="The validation captured here is absorbed by test_adhoc_1so_using_default_yml")
    def test_compose_1so_command_start(self):
        # Standup deployment
        self.compose_file_name = "1so_command_start.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
    
    @pytest.mark.skip(reason="The validation captured here is absorbed by test_adhoc_1uf_using_default_yml")
    def test_compose_1uf_command_start(self):
        # Standup deployment
        self.compose_file_name = "1uf_command_start.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)

    @pytest.mark.skip(reason="The validation captured here is absorbed by test_adhoc_1so_bind_mount_apps")
    def test_compose_1so_command_start_service(self):
        # Standup deployment
        self.compose_file_name = "1so_command_start_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
    
    @pytest.mark.skip(reason="The validation captured here is absorbed by test_adhoc_1uf_bind_mount_apps")
    def test_compose_1uf_command_start_service(self):
        # Standup deployment
        self.compose_file_name = "1uf_command_start_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)

    def test_compose_1so_java_oracle(self):
        # Standup deployment
        self.compose_file_name = "1so_java_oracle.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "oracle:8"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if java is installed
        exec_command = self.client.exec_create("so1", "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "java version \"1.8.0" in std_out

    def test_compose_1so_java_openjdk8(self):
        # Standup deployment
        self.compose_file_name = "1so_java_openjdk8.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "openjdk:8"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if java is installed
        exec_command = self.client.exec_create("so1", "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"1.8.0" in std_out

    def test_compose_1so_java_openjdk11(self):
        # Standup deployment
        self.compose_file_name = "1so_java_openjdk11.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "openjdk:11"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if java is installed
        exec_command = self.client.exec_create("so1", "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"11.0.2" in std_out

    def test_compose_1so_hec(self):
        # Standup deployment
        self.compose_file_name = "1so_hec.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec_token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check HEC works - note the token "abcd1234" is hard-coded within the 1so_hec.yaml compose
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 1
        so1 = containers[0]
        splunk_hec_port = self.client.port(so1["Id"], 8088)[0]["HostPort"]
        url = "https://localhost:{}/services/collector/event".format(splunk_hec_port)
        kwargs = {"json": {"event": "hello world"}, "verify": False, "headers": {"Authorization": "Splunk abcd1234"}}
        status, content = self.handle_request_retry("POST", url, kwargs)
        assert status == 200 

    def test_compose_1uf_hec(self):
        # Standup deployment
        self.compose_file_name = "1uf_hec.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec_token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check HEC works - note the token "abcd1234" is hard-coded within the 1so_hec.yaml compose
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 1
        uf1 = containers[0]
        splunk_hec_port = self.client.port(uf1["Id"], 8088)[0]["HostPort"]
        url = "https://localhost:{}/services/collector/event".format(splunk_hec_port)
        kwargs = {"json": {"event": "hello world"}, "verify": False, "headers": {"Authorization": "Splunk abcd1234"}}
        status, content = self.handle_request_retry("POST", url, kwargs)
        assert status == 200

    def test_compose_1so_enable_service(self):
        # Standup deployment
        self.compose_file_name = "1so_enable_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
        self.check_common_keys(log_json, "so")
        try:
            # enable_service is set in the compose file
            assert log_json["all"]["vars"]["splunk"]["enable_service"] == "true"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if service is registered
        exec_command = self.client.exec_create("so1", "sudo service splunk status")
        std_out = self.client.exec_start(exec_command)
        assert "splunkd is running" in std_out

    def test_compose_1uf_enable_service(self):
        # Standup deployment
        self.compose_file_name = "1uf_enable_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
        self.check_common_keys(log_json, "uf")
        try:
            # enable_service is set in the compose file
            assert log_json["all"]["vars"]["splunk"]["enable_service"] == "true"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if service is registered
        exec_command = self.client.exec_create("uf1", "sudo service splunk status")
        std_out = self.client.exec_start(exec_command)
        assert "splunkd is running" in std_out
    
    def test_compose_1so_apps(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1so_apps.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("so1")
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
        # Check container logs
        output = self.get_container_logs("so1")
        self.check_ansible(output)
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

    def test_compose_1uf_apps(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1uf_apps.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("uf1")
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
        # Check container logs
        output = self.get_container_logs("uf1")
        self.check_ansible(output)
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
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"so1": "so", "uf1": "uf"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs(container)
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json(container)
            self.check_common_keys(inventory_json, container_mapping[container])
            try:
                assert inventory_json["splunk_standalone"]["hosts"] == ["so1"]
            except KeyError as e:
                self.logger.error(e)
                raise e
        # Search results won't return the correct results immediately :(
        time.sleep(15)
        search_providers, distinct_hosts = self.search_internal_distinct_hosts("so1", password=self.password)
        assert len(search_providers) == 1
        assert search_providers[0] == "so1"
        assert distinct_hosts == 2

    def test_compose_1cm_smartstore(self):
        # Generate default.yml
        cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search("  password: (.*)", output).group(1).strip()
        assert password
        # Add a custom conf file
        output = re.sub(r'  smartstore: null', r'''  smartstore:
    - indexName: default
      remoteName: remote_vol
      scheme: s3
      remoteLocation: smartstore-test
      s3:
        access_key: abcd
        secret_key: 1234
        endpoint: https://s3-region.amazonaws.com''', output)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/tmp/defaults/default.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ROLE": "splunk_cluster_master",
                                                            "SPLUNK_INDEXER_URL": "idx1"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/default.yml:/tmp/defaults/default.yml"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
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
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass

    def test_compose_2idx2sh(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
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
        # Check connections
        idx_list = ["idx1", "idx2"]
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            c_name = container["Labels"]["com.docker.compose.service"]
            if c_name == "sh1" or c_name == "sh2":
                splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
                url = "https://localhost:{}/services/search/distributed/peers?output_mode=json".format(splunkd_port)
                kwargs = {"auth": ("admin", self.password), "verify": False}
                status, content = self.handle_request_retry("GET", url, kwargs)
                assert status == 200
                output = json.loads(content)
                peers = [x["content"]["peerName"] for x in output["entry"]]
                assert len(peers) == 2 and set(peers) == set(idx_list)
        # Search results won't return the correct results immediately :(
        time.sleep(15)
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
            # Wait for containers to come up
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
            time.sleep(15)
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
        
    def test_compose_2idx2sh1cm(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh1cm.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"sh1": "sh", "sh2": "sh", "idx1": "idx", "idx2": "idx", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs(container)
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json(container)
            self.check_common_keys(inventory_json, container_mapping[container])
            try:
                assert inventory_json["all"]["vars"]["splunk"]["indexer_cluster"] == True
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

        containers = self.client.containers(filters={"label": "com.docker.compose.service={}".format("cm1")})
        splunkd_port = self.client.port(containers[0]["Id"], 8089)[0]["HostPort"]
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
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, name="idx3")

        retries = 10
        for n in range(retries):
            status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/peers?output_mode=json".format(splunkd_port), 
                                                {"auth": ("admin", self.password), "verify": False})
            assert status == 200
            output = json.loads(content)
            for idx in output["entry"]:
                if idx["content"]["label"] == "idx3" and idx["content"]["status"] == "Up":
                    break
            else:
                time.sleep(10)
                if n < retries-1:
                    continue
                assert False
