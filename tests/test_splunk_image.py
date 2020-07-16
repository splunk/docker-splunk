#!/usr/bin/env python
# encoding: utf-8

#TODO: anything with conf is missing, add test_adhoc_1so_hec_custom_cert, test_adhoc_1uf_hec_custom_cert
#test_adhoc_1so_splunktcp_ssl, test_adhoc_1uf_splunktcp_ssl, test_adhoc_1so_splunkd_custom_ssl,
#test_adhoc_1uf_splunkd_custom_ssl, test_adhoc_1so_upgrade

import pytest
import time
import re
import os
import requests
import logging
import tarfile
import docker
import json
import yaml
import shlex
import subprocess
import logging.handlers
from shutil import copy, copytree, rmtree
from random import choice
from string import ascii_lowercase
from executor import Executor
from docker.types import Mount
# Code to suppress insecure https warnings
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)


global PLATFORM
PLATFORM = "debian-9"
OLD_SPLUNK_VERSION = "7.3.4"
FILE_DIR = os.path.dirname(os.path.realpath(__file__))
FIXTURES_DIR = os.path.join(FILE_DIR, "fixtures")
REPO_DIR = os.path.join(FILE_DIR, "..")
EXAMPLE_APP = os.path.join(FIXTURES_DIR, "splunk_app_example")
EXAMPLE_APP_TGZ = os.path.join(FIXTURES_DIR, "splunk_app_example.tgz")
SCENARIOS_DIR = os.path.join(FILE_DIR, "..", "test_scenarios")

# Setup logging
LOGGER = logging.getLogger("image_test")
LOGGER.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(os.path.join(FILE_DIR, "functional_image_test.log"), maxBytes=25000000)
formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] [%(process)d] %(message)s')
file_handler.setFormatter(formatter)
LOGGER.addHandler(file_handler)


def pytest_generate_tests(metafunc):
    # This is called for every test. Only get/set command line arguments
    # if the argument is specified in the list of test "fixturenames".
    option_value = metafunc.config.option.platform
    global PLATFORM
    PLATFORM = option_value

def generate_random_string():
    return ''.join(choice(ascii_lowercase) for b in range(20))


class TestDockerSplunk(Executor):

    @classmethod
    def setup_class(cls):
        cls.client = docker.APIClient()
        # Docker variables
        global PLATFORM
        cls.BASE_IMAGE_NAME = "base-{}".format(PLATFORM)
        cls.SPLUNK_IMAGE_NAME = "splunk-{}".format(PLATFORM)
        cls.UF_IMAGE_NAME = "uf-{}".format(PLATFORM)
        # Setup password
        cls.password = generate_random_string()
        with open(os.path.join(REPO_DIR, ".env"), "w") as f:
            f.write("SPLUNK_PASSWORD={}\n".format(cls.password))
            f.write("SPLUNK_IMAGE={}\n".format(cls.SPLUNK_IMAGE_NAME))
            f.write("UF_IMAGE={}\n".format(cls.UF_IMAGE_NAME))

    def wait_for_containers(self, count, label=None, name=None, timeout=10000):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''

        print("WAITING FOR CONTAINERS")
        start = time.time()
        end = start
        # Wait
        temp = 1
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
            if healthy_count == count:
                self.logger.info("All containers ready to proceed")
                break
            time.sleep(5)
            end = time.time()
            temp+=1
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

    def compose_up(self):
        container_count = self.get_number_of_containers(os.path.join(SCENARIOS_DIR, self.compose_file_name))
        command = "docker-compose -p {} -f test_scenarios/{} up -d".format(self.project_name, self.compose_file_name)
        out, err, rc = self._run_command(command)
        return container_count, rc

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
    
    def get_number_of_containers(self, filename):
        yml = {}
        with open(filename, "r") as f:
            yml = yaml.load(f, Loader=yaml.Loader)
        return len(yml["services"])

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

    def test_adhoc_1so_using_default_yml(self):
        splunk_container_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
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
        os.mkdir(DIR)
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[os.path.join(FIXTURES_DIR, splunk_container_name) + ":/tmp/defaults/"],
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
            print(splunkd_port, url, status)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(DIR, "default.yml"))
                os.rmdir(DIR)
            except OSError:
                pass

    def test_adhoc_1uf_using_default_yml(self):
        splunk_container_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
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
        os.mkdir(DIR)
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/"],
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
                os.remove(os.path.join(DIR, "default.yml"))
                os.rmdir(DIR)
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


TODO: Figure out how this works

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
        splunk_container_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
        DIR_EXAMPLE_APP = os.path.join(DIR, "splunk_app_example")
        copytree(EXAMPLE_APP, DIR_EXAMPLE_APP)
        EXAMPLE_APP_TGZ = os.path.join(DIR, "splunk_app_example.tgz")
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(DIR_EXAMPLE_APP, arcname=os.path.basename(DIR_EXAMPLE_APP))
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
        # os.mkdir(DIR)
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/"],
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
                os.remove(os.path.join(DIR, "default.yml"))
                rmtree(DIR)
            except OSError:
                pass

    def test_adhoc_1so_bind_mount_apps(self):
        # Generate default.yml
        splunk_container_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
        DIR_EXAMPLE_APP = os.path.join(DIR, "splunk_app_example")
        copytree(EXAMPLE_APP, DIR_EXAMPLE_APP)
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
                                            volumes=["/tmp/defaults/", "/opt/splunk/etc/apps/splunk_app_example/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/", 
                                                                                              DIR_EXAMPLE_APP + ":/opt/splunk/etc/apps/splunk_app_example/"],
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
                os.remove(os.path.join(DIR, "default.yml"))
                rmtree(DIR)
            except OSError:
                pass
    
    def test_adhoc_1uf_bind_mount_apps(self):
        # Generate default.yml
        splunk_container_name = generate_random_string()
        self.project_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
        DIR_EXAMPLE_APP = os.path.join(DIR, "splunk_app_example")
        copytree(EXAMPLE_APP, DIR_EXAMPLE_APP)
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        password = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert password and password != "null"
        # Write the default.yml to a file
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
                                            volumes=["/tmp/defaults/", "/opt/splunkforwarder/etc/apps/splunk_app_example/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/", 
                                                                                              DIR_EXAMPLE_APP + ":/opt/splunkforwarder/etc/apps/splunk_app_example/"],
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
                os.remove(os.path.join(DIR, "default.yml"))
                rmtree(DIR)
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

    def test_adhoc_1so_hec_idempotence(self):
        """
        This test is intended to check how the container gets provisioned with changing splunk.hec.* parameters
        """
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            self.project_name = generate_random_string()
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

    def test_adhoc_1so_hec_ssl_disabled(self):
        # Create the container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            self.project_name = generate_random_string()
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

    def test_adhoc_1uf_hec_ssl_disabled(self):
        # Create the container
        cid = None
        try:
            splunk_container_name = generate_random_string()
            self.project_name = generate_random_string()
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

    def test_adhoc_1so_splunkd_no_ssl(self):
        # Generate default.yml
        self.project_name = generate_random_string()
        splunk_container_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
        os.mkdir(DIR)
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
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_CERT_PREFIX": "http",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/"],
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
            rmtree(DIR)

    def test_adhoc_1uf_splunkd_no_ssl(self):
        # Generate default.yml
        self.project_name = generate_random_string()
        splunk_container_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
        os.mkdir(DIR)
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
        with open(os.path.join(DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_CERT_PREFIX": "http",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/"],
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
            rmtree(DIR)

    def test_adhoc_1so_web_ssl(self):
        # Generate a password
        password = generate_random_string()
        # Create the container
        splunk_container_name = generate_random_string()
        self.project_name = generate_random_string()
        DIR = os.path.join(FIXTURES_DIR, splunk_container_name)
        os.mkdir(DIR)
        cid = None
        try:
            # Commands to generate self-signed certificates for SplunkWeb here: https://docs.splunk.com/Documentation/Splunk/latest/Security/Self-signcertificatesforSplunkWeb
            cmd = "openssl req -x509 -newkey rsa:4096 -passout pass:abcd1234 -keyout {path}/key.pem -out {path}/cert.pem -days 365 -subj /CN=localhost".format(path=DIR)
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
                                            host_config=self.client.create_host_config(binds=[DIR + ":/tmp/defaults/"],
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
                os.remove(os.path.join(DIR, "key.pem"))
                os.remove(os.path.join(DIR, "cert.pem"))
                rmtree(DIR)
            except OSError:
                pass

    def test_compose_1so_trial(self):
        # Standup deployment
        self.compose_file_name = "1so_trial.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
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
        # delete container
        container = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        self.client.remove_container(container[0]["Id"], v=True, force=True)

    # def test_compose_1so_custombuild(self):
    #     # Standup deployment
    #     self.compose_file_name = "1so_custombuild.yaml"
    #     self.project_name = generate_random_string()
    #     container_count, rc = self.compose_up()
    #     # Wait for containers to come up
    #     assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
    #     # Check ansible inventory json
    #     log_json = self.extract_json("so1")
    #     self.check_common_keys(log_json, "so")
    #     # Check container logs
    #     output = self.get_container_logs("so1")
    #     self.check_ansible(output)
    #     # Check Splunkd on all the containers
    #     assert self.check_splunkd("admin", self.password)
    #     # delete container
    #     container = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
    #     self.client.remove_container(container[0]["Id"], v=True, force=True)