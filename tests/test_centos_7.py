#!/usr/bin/env python
# encoding: utf-8

import os
import re
import time
import pytest
import shlex
import yaml
import docker
import requests
import subprocess
import tarfile
import logging
import logging.handlers
import json
from random import choice
from string import ascii_lowercase
# Code to suppress insecure https warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import urllib3
urllib3.disable_warnings()


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
BASE_IMAGE_NAME = "base-centos-7"
SPLUNK_IMAGE_NAME = "splunk-centos-7"
UF_IMAGE_NAME = "splunkforwarder-centos-7"
# Splunk variables
SPLUNK_VERSION = "7.2.3"
SPLUNK_BUILD = "06d57c595b80"
SPLUNK_FILENAME = "splunk-{}-{}-Linux-x86_64.tgz".format(SPLUNK_VERSION, SPLUNK_BUILD)
SPLUNK_BUILD_URL = "https://download.splunk.com/products/splunk/releases/{}/linux/{}".format(SPLUNK_VERSION, SPLUNK_FILENAME)
UF_FILENAME = "splunkforwarder-{}-{}-Linux-x86_64.tgz".format(SPLUNK_VERSION, SPLUNK_BUILD)
UF_BUILD_URL = "https://download.splunk.com/products/universalforwarder/releases/{}/linux/{}".format(SPLUNK_VERSION, UF_FILENAME)
# Ansible version
ANSIBLE_VERSION = "2.7.5"

def generate_random_string():
    return ''.join(choice(ascii_lowercase) for b in range(20))


@pytest.mark.large
class TestCentos7(object):
    """
    Test suite to validate the Splunk Docker image
    """

    logger = LOGGER

    @classmethod
    def setup_class(cls):
        cls.client = docker.APIClient()
        # Build base
        response = cls.client.build(path=os.path.join(REPO_DIR, "base", "centos-7"), 
                                    buildargs={"SPLUNK_BUILD_URL": SPLUNK_BUILD_URL, "SPLUNK_FILENAME": SPLUNK_FILENAME},
                                    tag=BASE_IMAGE_NAME)
        for line in response:
            print line,
        # Build splunk
        response = cls.client.build(path=REPO_DIR, dockerfile=os.path.join("splunk", "centos-7", "Dockerfile"), 
                                    buildargs={"SPLUNK_BUILD_URL": SPLUNK_BUILD_URL, "SPLUNK_FILENAME": SPLUNK_FILENAME},
                                    tag=SPLUNK_IMAGE_NAME)
        for line in response:
            print line,
        # Build splunkforwarder
        response = cls.client.build(path=REPO_DIR, dockerfile=os.path.join("uf", "centos-7", "Dockerfile"), 
                                    buildargs={"SPLUNK_BUILD_URL": UF_BUILD_URL, "SPLUNK_FILENAME": UF_FILENAME},
                                    tag=UF_IMAGE_NAME)
        for line in response:
            print line,
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
        self.compose_file_name = ""

    def teardown_method(self, method):
        if self.compose_file_name:
            command = "docker-compose -p {} -f test_scenarios/{} down --volumes --remove-orphans".format(self.project_name, self.compose_file_name)
            out, err, rc = self._run_command(command)
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
    
    def wait_for_containers(self, count):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''
        start = time.time()
        end = start
        while end-start < 600:
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
            if len(containers) != count:
                return False
            healthy_count = 0
            for container in containers:
            	# If there's a healthcheck, validate healthy status
                if "(" in container["Status"] and "healthy" in container["Status"]:
                    healthy_count += 1
                # If there's no healthcheck, let it pass
                elif "(" not in container["Status"]:
                	healthy_count += 1
            if healthy_count == count:
                break
            time.sleep(10)
            end = time.time()
        return True

    def check_splunkd(self, username, password):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''
        retries = 5
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            for i in range(retries):
                self.logger.info("Attempt {} - checking splunkd on container {} at port {}".format(i, container["Names"][0], splunkd_port))
                try:
                    resp = requests.get("https://localhost:{}/services/server/info".format(splunkd_port),
                                    auth=(username, password), verify=False)
                    resp.raise_for_status()
                    break
                except Exception as e:
                    time.sleep(5)
                    if i < retries-1:
                        continue
                    self.logger.error(e)
                    return False
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
        retries = 5
        for i in range(retries):
            exec_command = self.client.exec_create(container_name, "cat opt/container_artifact/ansible_inventory.json")
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
        except KeyError as e:
            self.logger.error("{} key not found".format(e))            

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
                                            environment={"SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[FIXTURES_DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            self.client.start(cid.get("Id"))
            # Poll for the container to be healthy
            for _ in range(10):
                try:
                    containers = self.client.containers(filters={"name": splunk_container_name})
                    if "healthy" in containers[0]["Status"]:
                        break
                except Exception as e:
                    self.logger.error(e)
                finally:
                    time.sleep(5)
            # Check splunkd
            time.sleep(10)
            splunkd_port = self.client.port(cid.get("Id"), 8089)
            resp = requests.get("https://localhost:{}/services/server/info".format(splunkd_port[0]["HostPort"]), auth=("admin", password), verify=False)
            assert resp.status_code == 200
        except Exception as e:
            self.logger.error(e)
            assert False
        finally:
            if cid:
                self.client.remove_container(cid.get("Id"), v=True, force=True)
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
        assert self.wait_for_containers(container_count)
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
        assert self.wait_for_containers(container_count)
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
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
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
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")

    def test_compose_1so_command_start_service(self):
        # Standup deployment
        self.compose_file_name = "1so_command_start_service.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output)
        # Check values in log output
        self.check_common_keys(log_json, "so")

    def test_compose_1so_hec(self):
        # Standup deployment
        self.compose_file_name = "1so_hec.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")

        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
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
            assert False
        # Check HEC works - note the token "abcd1234" is hard-coded within the 1so_hec.yaml compose
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 1
        so1 = containers[0]
        splunk_hec_port = self.client.port(so1["Id"], 8088)
        retry_attempts = 10
        for i in range(retry_attempts):
            try:
                resp = requests.post("https://localhost:{}/services/collector/event".format(splunk_hec_port[0]["HostPort"]), 
                                     headers={"Authorization": "Splunk abcd1234"}, json={"event": "hello world"}, verify=False)
                assert resp.status_code == 200 
                break
            except Exception as e:
                self.logger.error(e)
                if i == retry_attempts-1:
                    assert False
            finally:
                time.sleep(5)

    def test_compose_1so_apps(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1so_apps.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        # Get container logs
        log_json = self.extract_json("so1")
        output = self.get_container_logs("so1")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
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
            assert False

        # Check to make sure the app got installed
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 2
        for container in containers:
            if "nginx" in container["Image"]:
                continue
            splunkd_port = self.client.port(container["Id"], 8089)
            retry_attempts = 10
            for i in range(retry_attempts):
                try:
                    resp = requests.get("https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port[0]["HostPort"]), 
                                        auth=("admin", self.password), verify=False)
                    assert resp.status_code == 200 
                    output = json.loads(resp.content)
                    assert output["entry"][0]["content"]["version"] == "0.0.1"
                    break
                except Exception as e:
                    self.logger.error(e)
                    if i == retry_attempts-1:
                        assert False
                finally:
                    time.sleep(5)
        try:
            os.remove(EXAMPLE_APP_TGZ)
        except OSError as e:
            pass

    def test_compose_1uf_hec(self):
        # Standup deployment
        self.compose_file_name = "1uf_hec.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        # Get container logs
        log_json = self.extract_json("uf1")
        output = self.get_container_logs("uf1")

        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
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
            assert False
        # Check HEC works - note the token "abcd1234" is hard-coded within the 1so_hec.yaml compose
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 1
        uf1 = containers[0]
        splunk_hec_port = self.client.port(uf1["Id"], 8088)
        retry_attempts = 10
        for i in range(retry_attempts):
            try:
                resp = requests.post("https://localhost:{}/services/collector/event".format(splunk_hec_port[0]["HostPort"]), 
                                     headers={"Authorization": "Splunk abcd1234"}, json={"event": "hello world"}, verify=False)
                assert resp.status_code == 200 
                break
            except Exception as e:
                self.logger.error(e)
                if i == retry_attempts-1:
                    assert False
            finally:
                time.sleep(5)

    def test_compose_1uf_apps(self):
        # Tar the app before spinning up the scenario
        with tarfile.open(EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(EXAMPLE_APP, arcname=os.path.basename(EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1uf_apps.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()
        # Get container logs
        log_json = self.extract_json("uf1")
        output = self.get_container_logs("uf1")

        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
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
            assert False

        # Check to make sure the app got installed
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        assert len(containers) == 2
        for container in containers:
            if "nginx" in container["Image"]:
                continue
            splunkd_port = self.client.port(container["Id"], 8089)
            retry_attempts = 10
            for i in range(retry_attempts):
                try:
                    resp = requests.get("https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port[0]["HostPort"]), 
                                        auth=("admin", self.password), verify=False)
                    assert resp.status_code == 200 
                    output = json.loads(resp.content)
                    assert output["entry"][0]["content"]["version"] == "0.0.1"
                    break
                except Exception as e:
                    self.logger.error(e)
                    if i == retry_attempts-1:
                        assert False
                finally:
                    time.sleep(5)
        try:
            os.remove(EXAMPLE_APP_TGZ)
        except OSError as e:
            pass

    def test_compose_1uf1so(self):
        # Standup deployment
        self.compose_file_name = "1uf1so.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()

        output_so = self.get_container_logs("so1")
        output_uf = self.get_container_logs("uf1")
        log_json_so = self.extract_json("so1")
        log_json_uf = self.extract_json("uf1")
    
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
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
            assert False

    def test_compose_2idx2sh(self):
        # Standup deployment
        self.compose_file_name = "2idx2sh.yaml"
        self.project_name = generate_random_string()
        container_count, rc = self.compose_up()

        output_sh1 = self.get_container_logs("sh1")
        output_sh2 = self.get_container_logs("sh2")
        output_idx1 = self.get_container_logs("idx1")
        output_idx2 = self.get_container_logs("idx2")
        log_json_sh1 = self.extract_json("sh1")
        log_json_sh2 = self.extract_json("sh2")
        log_json_idx1 = self.extract_json("idx1")
        log_json_idx2 = self.extract_json("idx2")
        assert rc == 0
        # Wait for containers to be healthy
        assert self.wait_for_containers(container_count)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check ansible version & configs
        self.check_ansible(output_sh1)
        self.check_ansible(output_sh2)
        self.check_ansible(output_idx1)
        self.check_ansible(output_idx2)
        # Check values in log output
        self.check_common_keys(log_json_sh1, "sh")
        self.check_common_keys(log_json_sh2, "sh")
        self.check_common_keys(log_json_idx1, "idx")
        self.check_common_keys(log_json_idx2, "idx")
        try:
            assert log_json_sh1["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
            assert log_json_sh1["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
            assert log_json_sh2["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
            assert log_json_sh2["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
            assert log_json_idx1["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
            assert log_json_idx1["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
            assert log_json_idx2["splunk_indexer"]["hosts"] == ["idx1", "idx2"]
            assert log_json_idx2["splunk_search_head"]["hosts"] == ["sh1", "sh2"]
        except KeyError as e:
            self.logger.error(e)
            assert False
