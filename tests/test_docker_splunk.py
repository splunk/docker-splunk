#!/usr/bin/env python
# encoding: utf-8

import os
import re
import time
import pytest
import shlex
import yaml
import docker
from docker.types import Mount
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
DEFAULTS_DIR = os.path.join(SCENARIOS_DIR, "defaults")
EXAMPLE_APP = os.path.join(FIXTURES_DIR, "splunk_app_example")
EXAMPLE_APP_TGZ = os.path.join(FIXTURES_DIR, "splunk_app_example.tgz")
# Setup logging
LOGGER = logging.getLogger("image_test")
LOGGER.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(os.path.join(FILE_DIR, "functional_image_test.log"), maxBytes=25000000)
formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] [%(process)d] %(message)s')
file_handler.setFormatter(formatter)
LOGGER.addHandler(file_handler)


global platform
platform = "debian-9"
OLD_SPLUNK_VERSION = "7.3.4"


def generate_random_string():
    return ''.join(choice(ascii_lowercase) for b in range(20))

def pytest_generate_tests(metafunc):
    # This is called for every test. Only get/set command line arguments
    # if the argument is specified in the list of test "fixturenames".
    option_value = metafunc.config.option.platform
    global platform
    platform = option_value


@pytest.mark.large
class TestDockerSplunk(object):
    """
    Test suite to validate the Splunk/UF Docker image
    """

    logger = LOGGER


    @classmethod
    def setup_class(cls):
        cls.client = docker.APIClient()
        # Docker variables
        global platform
        cls.BASE_IMAGE_NAME = "base-{}".format(platform)
        cls.SPLUNK_IMAGE_NAME = "splunk-{}".format(platform)
        cls.UF_IMAGE_NAME = "uf-{}".format(platform)
        # Setup password
        cls.password = generate_random_string()
        with open(os.path.join(REPO_DIR, ".env"), "w") as f:
            f.write("SPLUNK_PASSWORD={}\n".format(cls.password))
            f.write("SPLUNK_IMAGE={}\n".format(cls.SPLUNK_IMAGE_NAME))
            f.write("UF_IMAGE={}\n".format(cls.UF_IMAGE_NAME))

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

    def cleanup_files(self, files):
        try:
            for file in files:
                os.remove(file)
        except OSError as e:
            pass
        except Exception as e:
            raise e

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
    
    def wait_for_containers(self, count, label=None, name=None, timeout=300):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''
        start = time.time()
        end = start
        # Wait 
        while end-start < timeout:
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
        RETRIES = 10
        IMPLICIT_WAIT = 6
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

    def check_splunkd(self, username, password, name=None, scheme="https"):
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
            url = "{}://localhost:{}/services/server/info".format(scheme, splunkd_port)
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

    def _run_splunk_query(self, container_id, query, username="admin", password="password"):
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
        job_status = None
        url = "https://localhost:{}/services/search/jobs/{}?output_mode=json".format(splunkd_port, sid)
        kwargs = {
                    "auth": (username, password), 
                    "verify": False
                }
        for _ in range(10):
            job_status = requests.get(url, **kwargs)
            done = json.loads(job_status.content)["entry"][0]["content"]["isDone"]
            self.logger.info("Search job {} done status is {}".format(sid, done))
            if done:
                break
            time.sleep(3)
        assert job_status and job_status.status_code == 200
        # Get job metadata
        job_metadata = json.loads(job_status.content)
        # Check search results
        url = "https://localhost:{}/services/search/jobs/{}/results?output_mode=json".format(splunkd_port, sid)
        job_results = requests.get(url, **kwargs)
        assert job_results.status_code == 200
        job_results = json.loads(job_results.content)
        return job_metadata, job_results

    def search_internal_distinct_hosts(self, container_id, username="admin", password="password"):
        query = "search index=_internal earliest=-1m | stats dc(host) as distinct_hosts"
        meta, results = self._run_splunk_query(container_id, query, username, password)
        search_providers = meta["entry"][0]["content"]["searchProviders"]
        distinct_hosts = int(results["results"][0]["distinct_hosts"])
        return search_providers, distinct_hosts

    def check_common_keys(self, log_output, role):
        try:
            assert log_output["all"]["vars"]["ansible_ssh_user"] == "splunk"
            assert log_output["all"]["vars"]["ansible_pre_tasks"] == None
            assert log_output["all"]["vars"]["ansible_post_tasks"] == None
            assert log_output["all"]["vars"]["retry_num"] == 60
            assert log_output["all"]["vars"]["retry_delay"] == 6
            assert log_output["all"]["vars"]["wait_for_splunk_retry_num"] == 60
            assert log_output["all"]["vars"]["shc_sync_retry_num"] == 60
            assert log_output["all"]["vars"]["splunk"]["group"] == "splunk"
            assert log_output["all"]["vars"]["splunk"]["license_download_dest"] == "/tmp/splunk.lic"
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
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="help")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "SPLUNK_HOME - home directory where Splunk gets installed (default: /opt/splunk)" in output
        assert "Examples:" in output
    
    def test_splunk_entrypoint_create_defaults(self):
        # Run container
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "home: /opt/splunk" in output
        assert "password: " in output
        assert "secret: " in output
    
    def test_splunk_entrypoint_start_no_password(self):
        # Run container
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "WARNING: No password ENV var." in output
    
    def test_splunk_entrypoint_start_no_accept_license(self):
        # Run container
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_PASSWORD": "something", "SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "License not accepted, please ensure the environment variable SPLUNK_START_ARGS contains the '--accept-license' flag" in output

    def test_splunk_entrypoint_no_provision(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "cat /opt/ansible/version.txt")
            std_out = self.client.exec_start(exec_command)
            assert len(std_out.strip()) == 40
            # Check that the wrapper-example directory does not exist
            exec_command = self.client.exec_create(cid, "ls /opt/ansible/")
            std_out = self.client.exec_start(exec_command)
            assert "wrapper-example" not in std_out
            assert "docs" not in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_splunk_uid_gid(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "id", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "uid=41812" in std_out
            assert "gid=41812" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_splunk_uid_gid(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "id", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "uid=41812" in std_out
            assert "gid=41812" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_uf_entrypoint_help(self):
        # Run container
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="help")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "SPLUNK_CMD - 'any splunk command' - execute any splunk commands separated by commas" in output

    def test_uf_entrypoint_create_defaults(self):
        # Run container
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "home: /opt/splunk" in output
        assert "password: " in output
    
    def test_uf_entrypoint_start_no_password(self):
        # Run container
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "WARNING: No password ENV var." in output
    
    def test_uf_entrypoint_start_no_accept_license(self):
        # Run container
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start",
                                           environment={"SPLUNK_PASSWORD": "something", "SPLUNK_START_ARGS": "nothing"})
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "License not accepted, please ensure the environment variable SPLUNK_START_ARGS contains the '--accept-license' flag" in output

    def test_uf_entrypoint_no_provision(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "cat /opt/ansible/version.txt")
            std_out = self.client.exec_start(exec_command)
            assert len(std_out.strip()) == 40
            # Check that the wrapper-example directory does not exist
            exec_command = self.client.exec_create(cid, "ls /opt/ansible/")
            std_out = self.client.exec_start(exec_command)
            assert "wrapper-example" not in std_out
            assert "docs" not in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_uf_uid_gid(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "id", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "uid=41812" in std_out
            assert "gid=41812" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_uf_uid_gid(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the git SHA exists in /opt/ansible
            exec_command = self.client.exec_create(cid, "id", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "uid=41812" in std_out
            assert "gid=41812" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_adhoc_1so_using_default_yml(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Change the admin user
        output = re.sub(r'  admin_user: admin', r'  admin_user: chewbacca', output)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
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
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Change the admin user
        output = re.sub(r'  admin_user: admin', r'  admin_user: hansolo', output)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start", ports=[8089], 
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
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
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
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
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
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
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
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start", ports=[8089], 
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
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
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

    def test_adhoc_1so_splunk_launch_conf(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_LAUNCH_CONF": "OPTIMISTIC_ABOUT_FILE_LOCKING=1,HELLO=WORLD"
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check splunk-launch.conf
            exec_command = self.client.exec_create(cid, r'cat /opt/splunk/etc/splunk-launch.conf', user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "OPTIMISTIC_ABOUT_FILE_LOCKING=1" in std_out
            assert "HELLO=WORLD" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_change_tailed_files(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_TAIL_FILE": "/opt/splunk/var/log/splunk/web_access.log /opt/splunk/var/log/splunk/first_install.log"
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check the tailed logs
            logs = self.client.logs(cid, tail=20)
            assert "==> /opt/splunk/var/log/splunk/first_install.log <==" in logs
            assert "==> /opt/splunk/var/log/splunk/web_access.log <==" in logs
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1uf_change_tailed_files(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], 
                                            name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_TAIL_FILE": "/opt/splunkforwarder/var/log/splunk/splunkd_stderr.log /opt/splunkforwarder/var/log/splunk/first_install.log"
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check the tailed logs
            logs = self.client.logs(cid, tail=20)
            assert "==> /opt/splunkforwarder/var/log/splunk/first_install.log <==" in logs
            assert "==> /opt/splunkforwarder/var/log/splunk/splunkd_stderr.log <==" in logs
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_password_from_file(self):
        # Create a splunk container
        cid = None
        # From fixtures/pwfile
        filePW = "changeme123"
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/var/secrets/pwfile"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": "/var/secrets/pwfile"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/pwfile:/var/secrets/pwfile"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", filePW), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_adhoc_1uf_password_from_file(self):
        # Create a splunk container
        cid = None
        # From fixtures/pwfile
        filePW = "changeme123"
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/var/secrets/pwfile"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": "/var/secrets/pwfile"
                                                        },
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + "/pwfile:/var/secrets/pwfile"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", filePW), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_reflexive_forwarding(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            # When adding SPLUNK_STANDALONE_URL to the standalone, we shouldn't have any situation where it starts forwarding/disables indexing
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_STANDALONE_URL": splunk_container_name
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check the decrypted pass4SymmKey
            exec_command = self.client.exec_create(cid, "ls /opt/splunk/etc/system/local/", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "outputs.conf" not in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_splunk_pass4symmkey(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_PASS4SYMMKEY": "wubbalubbadubdub"
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check the decrypted pass4SymmKey
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            pass4SymmKey = re.search(r'\[general\].*?pass4SymmKey = (.*?)\n', std_out, flags=re.MULTILINE|re.DOTALL).group(1).strip()
            exec_command = self.client.exec_create(cid, "/opt/splunk/bin/splunk show-decrypted --value '{}'".format(pass4SymmKey), user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "wubbalubbadubdub" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_splunk_secret_env(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_SECRET": "wubbalubbadubdub"
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/auth/splunk.secret", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "wubbalubbadubdub" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
    
    def test_adhoc_1uf_splunk_pass4symmkey(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_PASS4SYMMKEY": "wubbalubbadubdub"
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check the decrypted pass4SymmKey
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            pass4SymmKey = re.search(r'\[general\].*?pass4SymmKey = (.*?)\n', std_out, flags=re.MULTILINE|re.DOTALL).group(1).strip()
            exec_command = self.client.exec_create(cid, "/opt/splunkforwarder/bin/splunk show-decrypted --value '{}'".format(pass4SymmKey), user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "wubbalubbadubdub" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1uf_splunk_secret_env(self):
        # Create a uf container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_SECRET": "wubbalubbadubdub"
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/auth/splunk.secret", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "wubbalubbadubdub" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_preplaybook_with_sudo(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
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
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
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
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
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

    def test_adhoc_1so_apps_location_in_default_yml(self):
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Change repl factor & search factor
        output = re.sub(r'  user: splunk', r'  user: splunk\n  apps_location: /tmp/defaults/splunk_app_example.tgz', output)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
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
                os.remove(EXAMPLE_APP_TGZ)
                os.remove(os.path.join(FIXTURES_DIR, "default.yml"))
            except OSError:
                pass

    def test_adhoc_1so_bind_mount_apps(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
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
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
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
            assert self.check_splunkd("admin", password)
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

    def test_adhoc_1so_run_as_root(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name, user="root",
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_USER": "root",
                                                            "SPLUNK_GROUP": "root"
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check that root owns the splunkd process
            exec_command = self.client.exec_create(cid, "ps -u root", user="root")
            std_out = self.client.exec_start(exec_command)
            assert "entrypoint.sh" in std_out
            assert "splunkd" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1uf_run_as_root(self):
        # Create a uf container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name, user="root",
                                               environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_USER": "root",
                                                            "SPLUNK_GROUP": "root"
                                                        },
                                               host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
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
            # Check that root owns the splunkd process
            exec_command = self.client.exec_create(cid, "ps -u root", user="root")
            std_out = self.client.exec_start(exec_command)
            assert "entrypoint.sh" in std_out
            assert "splunkd" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_hec_idempotence(self):
        """
        This test is intended to check how the container gets provisioned with changing splunk.hec.* parameters
        """
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089, 8088, 9999], 
                                            name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",), 9999: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", self.password)
            # Check that HEC endpoint is up - by default, the image will enable HEC
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert std_out == '''[http]
disabled = 0
'''
            exec_command = self.client.exec_create(cid, "netstat -tuln", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "tcp        0      0 0.0.0.0:8088            0.0.0.0:*               LISTEN" in std_out
            # Create a new /tmp/defaults/default.yml to change desired HEC settings
            exec_command = self.client.exec_create(cid, "mkdir -p /tmp/defaults", user="splunk")
            self.client.exec_start(exec_command)
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  hec:
    port: 9999
    token: hihihi
    ssl: False
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Restart the container - it should pick up the new HEC settings in /tmp/defaults/default.yml
            self.client.restart(splunk_container_name)
            assert self.wait_for_containers(1, name=splunk_container_name)
            assert self.check_splunkd("admin", self.password)
            # Check the new HEC settings
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert '''[http]
disabled = 0
enableSSL = 0
port = 9999''' in std_out
            assert '''[http://splunk_hec_token]
disabled = 0
token = hihihi''' in std_out
            exec_command = self.client.exec_create(cid, "netstat -tuln", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "tcp        0      0 0.0.0.0:9999            0.0.0.0:*               LISTEN" in std_out
            # Check HEC
            hec_port = self.client.port(cid, 9999)[0]["HostPort"]
            url = "http://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk hihihi"}}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
            # Modify the HEC configuration
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  hec:
    port: 8088
    token: byebyebye
    ssl: True
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Restart the container - it should pick up the new HEC settings in /tmp/defaults/default.yml
            self.client.restart(splunk_container_name)
            assert self.wait_for_containers(1, name=splunk_container_name)
            assert self.check_splunkd("admin", self.password)
            # Check the new HEC settings
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert '''[http]
disabled = 0
enableSSL = 1
port = 8088''' in std_out
            assert '''[http://splunk_hec_token]
disabled = 0
token = byebyebye''' in std_out
            exec_command = self.client.exec_create(cid, "netstat -tuln", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "tcp        0      0 0.0.0.0:8088            0.0.0.0:*               LISTEN" in std_out
            # Check HEC
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "https://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk byebyebye"}, "verify": False}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
            # Remove the token
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  hec:
    token:
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Restart the container - it should pick up the new HEC settings in /tmp/defaults/default.yml
            self.client.restart(splunk_container_name)
            assert self.wait_for_containers(1, name=splunk_container_name)
            assert self.check_splunkd("admin", self.password)
            # Check the new HEC settings
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            # NOTE: The previous configuration still applies - we just deleted the former token
            assert '''[http]
disabled = 0
enableSSL = 1
port = 8088''' in std_out
            assert "[http://splunk_hec_token]" not in std_out
            exec_command = self.client.exec_create(cid, "netstat -tuln", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "tcp        0      0 0.0.0.0:8088            0.0.0.0:*               LISTEN" in std_out
            # Disable HEC entirely
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  hec:
    enable: False
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Restart the container - it should pick up the new HEC settings in /tmp/defaults/default.yml
            self.client.restart(splunk_container_name)
            assert self.wait_for_containers(1, name=splunk_container_name)
            assert self.check_splunkd("admin", self.password)
            # Check the new HEC settings
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert '''[http]
disabled = 1''' in std_out
            exec_command = self.client.exec_create(cid, "netstat -tuln", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "tcp        0      0 0.0.0.0:8088            0.0.0.0:*               LISTEN" not in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1so_hec_custom_cert(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "glootie"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=FIXTURES_DIR)
            ]
        for cmd in cmds:
            execute_cmd = subprocess.check_output(["/bin/sh", "-c", cmd])
        # Update s2s ssl settings
        output = re.sub(r'''  hec:.*?    token: .*?\n''', r'''  hec:
    enable: True
    port: 8088
    ssl: True
    token: doyouwannadevelopanapp
    cert: /tmp/defaults/cert.pem
    password: {}\n'''.format(passphrase), output, flags=re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            password = "helloworld"
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8088, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[http://splunk_hec_token]" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            assert "sslPassword = " in std_out
            # Check HEC using the custom certs
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "https://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk doyouwannadevelopanapp"}, "verify": "{}/cacert.pem".format(FIXTURES_DIR)}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [
                        os.path.join(FIXTURES_DIR, "ca.key"),
                        os.path.join(FIXTURES_DIR, "ca.csr"),
                        os.path.join(FIXTURES_DIR, "ca.pem"),
                        os.path.join(FIXTURES_DIR, "cacert.pem"),
                        os.path.join(FIXTURES_DIR, "server.key"),
                        os.path.join(FIXTURES_DIR, "server.csr"),
                        os.path.join(FIXTURES_DIR, "server.pem"),
                        os.path.join(FIXTURES_DIR, "cert.pem"),
                        os.path.join(FIXTURES_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_adhoc_1uf_hec_custom_cert(self):
        # Generate default.yml
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "glootie"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=FIXTURES_DIR)
            ]
        for cmd in cmds:
            execute_cmd = subprocess.check_output(["/bin/sh", "-c", cmd])
        # Update s2s ssl settings
        output = re.sub(r'''  hec:.*?    token: .*?\n''', r'''  hec:
    enable: True
    port: 8088
    ssl: True
    token: doyouwannadevelopanapp
    cert: /tmp/defaults/cert.pem
    password: {}\n'''.format(passphrase), output, flags=re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            password = "helloworld"
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8088, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[http://splunk_hec_token]" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            assert "sslPassword = " in std_out
            # Check HEC using the custom certs
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "https://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk doyouwannadevelopanapp"}, "verify": "{}/cacert.pem".format(FIXTURES_DIR)}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [
                        os.path.join(FIXTURES_DIR, "ca.key"),
                        os.path.join(FIXTURES_DIR, "ca.csr"),
                        os.path.join(FIXTURES_DIR, "ca.pem"),
                        os.path.join(FIXTURES_DIR, "cacert.pem"),
                        os.path.join(FIXTURES_DIR, "server.key"),
                        os.path.join(FIXTURES_DIR, "server.csr"),
                        os.path.join(FIXTURES_DIR, "server.pem"),
                        os.path.join(FIXTURES_DIR, "cert.pem"),
                        os.path.join(FIXTURES_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_adhoc_1so_hec_ssl_disabled(self):
        # Create the container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089, 8088], 
                                            name=splunk_container_name,
                                            environment={
                                                "DEBUG": "true", 
                                                "SPLUNK_START_ARGS": "--accept-license",
                                                "SPLUNK_HEC_TOKEN": "get-schwifty",
                                                "SPLUNK_HEC_SSL": "False",
                                                "SPLUNK_PASSWORD": self.password
                                            },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", self.password)
            # Check HEC
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "http://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk get-schwifty"}}
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
        # Create the container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089, 8088], 
                                            name=splunk_container_name,
                                            environment={
                                                "DEBUG": "true", 
                                                "SPLUNK_START_ARGS": "--accept-license",
                                                "SPLUNK_HEC_TOKEN": "get-schwifty",
                                                "SPLUNK_HEC_SSL": "false",
                                                "SPLUNK_PASSWORD": self.password
                                            },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", self.password)
            # Check HEC
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "http://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk get-schwifty"}}
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

    def test_adhoc_1so_splunktcp_ssl(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "abcd1234"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=FIXTURES_DIR)
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
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[splunktcp-ssl:9997]" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [
                        os.path.join(FIXTURES_DIR, "ca.key"),
                        os.path.join(FIXTURES_DIR, "ca.csr"),
                        os.path.join(FIXTURES_DIR, "ca.pem"),
                        os.path.join(FIXTURES_DIR, "server.key"),
                        os.path.join(FIXTURES_DIR, "server.csr"),
                        os.path.join(FIXTURES_DIR, "server.pem"),
                        os.path.join(FIXTURES_DIR, "cert.pem"),
                        os.path.join(FIXTURES_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_adhoc_1uf_splunktcp_ssl(self):
        # Generate default.yml
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "abcd1234"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=FIXTURES_DIR)
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
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/system/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[splunktcp-ssl:9997]" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [
                        os.path.join(FIXTURES_DIR, "ca.key"),
                        os.path.join(FIXTURES_DIR, "ca.csr"),
                        os.path.join(FIXTURES_DIR, "ca.pem"),
                        os.path.join(FIXTURES_DIR, "server.key"),
                        os.path.join(FIXTURES_DIR, "server.csr"),
                        os.path.join(FIXTURES_DIR, "server.pem"),
                        os.path.join(FIXTURES_DIR, "cert.pem"),
                        os.path.join(FIXTURES_DIR, "cacert.pem"),
                        os.path.join(FIXTURES_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_adhoc_1so_splunkd_custom_ssl(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "heyallyoucoolcatsandkittens"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=FIXTURES_DIR)
            ]
        for cmd in cmds:
            execute_cmd = subprocess.check_output(["/bin/sh", "-c", cmd])
        # Update server ssl settings
        output = re.sub(r'''^  ssl:.*?password: null''', r'''  ssl:
    ca: /tmp/defaults/ca.pem
    cert: /tmp/defaults/cert.pem
    enable: true
    password: {}'''.format(passphrase), output, flags=re.MULTILINE|re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "sslRootCAPath = /tmp/defaults/ca.pem" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", password), "verify": "{}/cacert.pem".format(FIXTURES_DIR)}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [
                        os.path.join(FIXTURES_DIR, "ca.key"),
                        os.path.join(FIXTURES_DIR, "ca.csr"),
                        os.path.join(FIXTURES_DIR, "ca.pem"),
                        os.path.join(FIXTURES_DIR, "server.key"),
                        os.path.join(FIXTURES_DIR, "server.csr"),
                        os.path.join(FIXTURES_DIR, "server.pem"),
                        os.path.join(FIXTURES_DIR, "cert.pem"),
                        os.path.join(FIXTURES_DIR, "cacert.pem"),
                        os.path.join(FIXTURES_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_adhoc_1uf_splunkd_custom_ssl(self):
        # Generate default.yml
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "heyallyoucoolcatsandkittens"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=FIXTURES_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=FIXTURES_DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=FIXTURES_DIR)
            ]
        for cmd in cmds:
            execute_cmd = subprocess.check_output(["/bin/sh", "-c", cmd])
        # Update server ssl settings
        output = re.sub(r'''^  ssl:.*?password: null''', r'''  ssl:
    ca: /tmp/defaults/ca.pem
    cert: /tmp/defaults/cert.pem
    enable: true
    password: {}'''.format(passphrase), output, flags=re.MULTILINE|re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "sslRootCAPath = /tmp/defaults/ca.pem" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", password), "verify": "{}/cacert.pem".format(FIXTURES_DIR)}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [
                        os.path.join(FIXTURES_DIR, "ca.key"),
                        os.path.join(FIXTURES_DIR, "ca.csr"),
                        os.path.join(FIXTURES_DIR, "ca.pem"),
                        os.path.join(FIXTURES_DIR, "server.key"),
                        os.path.join(FIXTURES_DIR, "server.csr"),
                        os.path.join(FIXTURES_DIR, "server.pem"),
                        os.path.join(FIXTURES_DIR, "cert.pem"),
                        os.path.join(FIXTURES_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_adhoc_1so_splunkd_no_ssl(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Update server ssl settings
        output = re.sub(r'''^  ssl:.*?password: null''', r'''  ssl:
    ca: null
    cert: null
    enable: false
    password: null''', output, flags=re.MULTILINE|re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_CERT_PREFIX": "http",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, scheme="http")
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "enableSplunkdSSL = false" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "http://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", password)}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [os.path.join(FIXTURES_DIR, "default.yml")]
            self.cleanup_files(files)

    def test_adhoc_1uf_splunkd_no_ssl(self):
        # Generate default.yml
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Update server ssl settings
        output = re.sub(r'''^  ssl:.*?password: null''', r'''  ssl:
    ca: null
    cert: null
    enable: false
    password: null''', output, flags=re.MULTILINE|re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_CERT_PREFIX": "http",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, scheme="http")
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "enableSplunkdSSL = false" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "http://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", password)}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            files = [os.path.join(FIXTURES_DIR, "default.yml")]
            self.cleanup_files(files)

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
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
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

    def test_adhoc_1so_upgrade(self):
        # Pull the old image
        for line in self.client.pull("splunk/splunk:{}".format(OLD_SPLUNK_VERSION), stream=True, decode=True):
            continue
        # Create the "splunk-old" container
        try:
            cid = None
            splunk_container_name = generate_random_string()
            user, password = "admin", generate_random_string()
            cid = self.client.create_container("splunk/splunk:{}".format(OLD_SPLUNK_VERSION), tty=True, ports=[8089, 8088], hostname="splunk",
                                            name=splunk_container_name, environment={"DEBUG": "true", "SPLUNK_HEC_TOKEN": "qwerty", "SPLUNK_PASSWORD": password, "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(mounts=[Mount("/opt/splunk/etc", "opt-splunk-etc"), Mount("/opt/splunk/var", "opt-splunk-var")],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd(user, password)
            # Add some data via HEC
            splunk_hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "https://localhost:{}/services/collector/event".format(splunk_hec_port)
            kwargs = {"json": {"event": "world never says hello back"}, "verify": False, "headers": {"Authorization": "Splunk qwerty"}}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
            # Sleep to let the data index
            time.sleep(3)
            # Remove the "splunk-old" container
            self.client.remove_container(cid, v=False, force=True)
            # Create the "splunk-new" container re-using volumes
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089, 8000], hostname="splunk",
                                            name=splunk_container_name, environment={"DEBUG": "true", "SPLUNK_HEC_TOKEN": "qwerty", "SPLUNK_PASSWORD": password, "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(mounts=[Mount("/opt/splunk/etc", "opt-splunk-etc"), Mount("/opt/splunk/var", "opt-splunk-var")],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd(user, password)
            # Run a search
            time.sleep(3)
            query = "search index=main earliest=-10m"
            meta, results = self._run_splunk_query(cid, query, user, password)
            results = results["results"]
            assert len(results) == 1
            assert results[0]["_raw"] == "world never says hello back"
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

    def test_compose_1deployment1cm(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))

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
        with open(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "1deployment1cm.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"cm1": "cm", "depserver1": "deployment_server"}
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
                container_name = container["Names"][0].strip("/")
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
                    # Check that the app exists in etc/deployment-apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/deployment-apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" not in std_out
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
            # Make sure apps are installed and certain subdirectories are excluded
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            assert len(containers) == 3
            for container in containers:
                # Skip the nginx container
                if "nginx" in container["Image"]:
                    continue
                container_name = container["Names"][0].strip("/")
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
                    # Check that the app exists in etc/deployment-apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/deployment-apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" not in std_out
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

    def test_compose_1deployment1uf(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        try:
            self.compose_file_name = "1deployment1uf.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
            # Get container logs
            container_mapping = {"uf1": "uf", "depserver1": "deployment_server"}
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
                    # Check that the app exists in etc/deployment-apps
                    exec_command = self.client.exec_create(container["Id"], "ls /opt/splunk/etc/deployment-apps/splunk_app_example/local/", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "savedsearches.conf" not in std_out
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
        # Restart the container and make sure java is still installed
        self.client.restart("so1")
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        assert self.check_splunkd("admin", self.password)
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
        # Restart the container and make sure java is still installed
        self.client.restart("so1")
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        assert self.check_splunkd("admin", self.password)
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
        # Restart the container and make sure java is still installed
        self.client.restart("so1")
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        assert self.check_splunkd("admin", self.password)
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
            assert log_json["all"]["vars"]["splunk"]["hec"]["token"] == "abcd1234"
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
            assert log_json["all"]["vars"]["splunk"]["hec"]["token"] == "abcd1234"
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
        if 'debian' in platform:
            exec_command = self.client.exec_create("so1", "sudo service splunk status")
            std_out = self.client.exec_start(exec_command)
            assert "splunkd is running" in std_out
        else:
            exec_command = self.client.exec_create("so1", "stat /etc/init.d/splunk")
            std_out = self.client.exec_start(exec_command)
            assert "/etc/init.d/splunk" in std_out

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
        if 'debian' in platform:
            exec_command = self.client.exec_create("uf1", "sudo service splunk status")
            std_out = self.client.exec_start(exec_command)
            assert "splunkd is running" in std_out
        else:
            exec_command = self.client.exec_create("uf1", "stat /etc/init.d/splunk")
            std_out = self.client.exec_start(exec_command)
            assert "/etc/init.d/splunk" in std_out
    
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

    def test_compose_3idx1cm_splunktcp_ssl(self):
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
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=DEFAULTS_DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=DEFAULTS_DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=DEFAULTS_DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=DEFAULTS_DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=DEFAULTS_DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=DEFAULTS_DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=DEFAULTS_DIR)
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
        with open(os.path.join(DEFAULTS_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "3idx1cm.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"cm1": "cm", "idx1": "idx", "idx2": "idx", "idx3": "idx"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs(container)
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json(container)
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
                container_name = container["Names"][0].strip("/")
                cid = container["Id"]
                exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/inputs.conf", user="splunk")
                std_out = self.client.exec_start(exec_command)
                assert "[splunktcp-ssl:9997]" in std_out
                assert "disabled = 0" in std_out
                assert "[SSL]" in std_out
                assert "serverCert = /tmp/defaults/cert.pem" in std_out
                assert "[sslConfig]" in std_out
                assert "rootCA = /tmp/defaults/ca.pem" in std_out
                if container_name == "cm1":
                    exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/outputs.conf", user="splunk")
                    std_out = self.client.exec_start(exec_command)
                    assert "clientCert = /tmp/defaults/cert.pem" in std_out
                    assert "sslPassword" in std_out
                    assert "useClientSSLCompression = true" in std_out
                    # Check that data is being forwarded properly
                    time.sleep(15)
                    search_providers, distinct_hosts = self.search_internal_distinct_hosts("cm1", password=self.password)
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
                        os.path.join(DEFAULTS_DIR, "ca.key"),
                        os.path.join(DEFAULTS_DIR, "ca.csr"),
                        os.path.join(DEFAULTS_DIR, "ca.pem"),
                        os.path.join(DEFAULTS_DIR, "server.key"),
                        os.path.join(DEFAULTS_DIR, "server.csr"),
                        os.path.join(DEFAULTS_DIR, "server.pem"),
                        os.path.join(DEFAULTS_DIR, "cert.pem"),
                        os.path.join(DEFAULTS_DIR, "default.yml")
                    ]
            self.cleanup_files(files)

    def test_compose_3idx1cm_default_repl_factor(self):
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "3idx1cm.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"cm1": "cm", "idx1": "idx", "idx2": "idx", "idx3": "idx"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs(container)
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json(container)
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
                container_name = container["Names"][0].strip("/")
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
                os.remove(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"))
            except OSError as e:
                pass

    def test_compose_3idx1cm_custom_repl_factor(self):
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
        with open(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"), "w") as f:
            f.write(output)
        # Standup deployment
        try:
            self.compose_file_name = "3idx1cm.yaml"
            self.project_name = generate_random_string()
            container_count, rc = self.compose_up()
            assert rc == 0
            # Wait for containers to come up
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
            # Get container logs
            container_mapping = {"cm1": "cm", "idx1": "idx", "idx2": "idx", "idx3": "idx"}
            for container in container_mapping:
                # Check ansible version & configs
                ansible_logs = self.get_container_logs(container)
                self.check_ansible(ansible_logs)
                # Check values in log output
                inventory_json = self.extract_json(container)
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
                container_name = container["Names"][0].strip("/")
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
                os.remove(os.path.join(SCENARIOS_DIR, "defaults", "default.yml"))
            except OSError as e:
                pass

    def test_compose_1so1cm_connected(self):
        # Standup deployment
        self.compose_file_name = "1so1cm_connected.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"so1": "so", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs(container)
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json(container)
            self.check_common_keys(inventory_json, container_mapping[container])
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        containers = self.client.containers(filters={"label": "com.docker.compose.service={}".format("cm1")})
        splunkd_port = self.client.port(containers[0]["Id"], 8089)[0]["HostPort"]
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
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"so1": "so", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs(container)
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json(container)
            self.check_common_keys(inventory_json, container_mapping[container])
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        containers = self.client.containers(filters={"label": "com.docker.compose.service={}".format("cm1")})
        splunkd_port = self.client.port(containers[0]["Id"], 8089)[0]["HostPort"]
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
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], name=splunk_container_name,
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
            assert self.wait_for_containers(1, name=splunk_container_name)
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
        with open(os.path.join(FIXTURES_DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
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

    def test_compose_1sh1cm(self):
        # Standup deployment
        self.compose_file_name = "1sh1cm.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Get container logs
        container_mapping = {"sh1": "sh", "cm1": "cm"}
        for container in container_mapping:
            # Check ansible version & configs
            ansible_logs = self.get_container_logs(container)
            self.check_ansible(ansible_logs)
            # Check values in log output
            inventory_json = self.extract_json(container)
            self.check_common_keys(inventory_json, container_mapping[container])
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check connections
        containers = self.client.containers(filters={"label": "com.docker.compose.service={}".format("cm1")})
        splunkd_port = self.client.port(containers[0]["Id"], 8089)[0]["HostPort"]
        status, content = self.handle_request_retry("GET", "https://localhost:{}/services/cluster/master/searchheads?output_mode=json".format(splunkd_port), 
                                                    {"auth": ("admin", self.password), "verify": False})
        assert status == 200
        output = json.loads(content)
        # There's only 1 "standalone" search head connected and 1 cluster master
        assert len(output["entry"]) == 2
        for sh in output["entry"]:
            assert sh["content"]["label"] == "sh1" or sh["content"]["label"] == "cm1"
            assert sh["content"]["status"] == "Connected"

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
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
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
            assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name), timeout=600)
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
            time.sleep(30)
            RETRIES = 10
            IMPLICIT_WAIT = 6
            for n in range(RETRIES):
                try:
                    self.logger.info("Attempt #{}: checking internal search host count".format(n+1))
                    search_providers, distinct_hosts = self.search_internal_distinct_hosts("sh1", password=self.password)
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
