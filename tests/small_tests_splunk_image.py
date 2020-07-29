#!/usr/bin/env python
# encoding: utf-8

import pytest
import time
import re
import os
import tarfile
import docker
import json
import urllib
import yaml
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

os.environ['COMPOSE_HTTP_TIMEOUT']='500'
os.environ['DOCKER_CLIENT_TIMEOUT']='500'

def pytest_generate_tests(metafunc):
    # This is called for every test. Only get/set command line arguments
    # if the argument is specified in the list of test "fixturenames".
    option_value = metafunc.config.option.platform
    global PLATFORM
    PLATFORM = option_value


class TestDockerSplunk(Executor):

    @classmethod
    def setup_class(cls):
        cls.client = docker.APIClient()
        # Docker variables
        global PLATFORM
        cls.BASE_IMAGE_NAME = "base-{}".format(PLATFORM)
        cls.SPLUNK_IMAGE_NAME = "splunk-{}".format(PLATFORM)
        cls.UF_IMAGE_NAME = "uf-{}".format(PLATFORM)
        cls.password = cls.generate_random_string()
        cls.compose_file_name = None
        cls.project_name = None
        cls.DIR = None

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

    def test_compose_1so_trial(self):
        # Standup deployment
        self.compose_file_name = "1so_trial.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs1("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)

    def test_compose_1so_custombuild(self):
        # Standup deployment
        self.compose_file_name = "1so_custombuild.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs1("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)

    def test_compose_1so_namedvolumes(self):
        # TODO: We can do a lot better in this test - ex. check that data is persisted after restarts
        # Standup deployment
        self.compose_file_name = "1so_namedvolumes.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs1("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)

    def test_compose_1so_before_start_cmd(self):
        # Check that SPLUNK_BEFORE_START_CMD works for splunk image
        # Standup deployment
        self.compose_file_name = "1so_before_start_cmd.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs1("so1")
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
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs1("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("normalplebe", "newpassword")
    
    def test_compose_1so_splunk_add(self):
        # Check that SPLUNK_ADD works for splunk image (role=standalone)
        # Standup deployment
        self.compose_file_name = "1so_splunk_add_user.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("so1")
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs1("so1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("newman", "changemepls")

    def test_compose_1hf_splunk_add(self):
        # Check that SPLUNK_ADD works for splunk image (role=heavy forwarder)
        # Standup deployment
        self.compose_file_name = "1hf_splunk_add_user.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("hf1")
        self.check_common_keys(log_json, "hf")
        # Check container logs
        output = self.get_container_logs1("hf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("jerry", "seinfeld")

    def test_compose_1uf_splunk_add(self):
        # Check that SPLUNK_ADD works for splunkforwarder image
        # Standup deployment
        self.compose_file_name = "1uf_splunk_add_user.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs1("uf1")
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
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("uf1")
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs1("uf1")
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("jerry", "changemepls")
        assert self.check_splunkd("george", "changemepls")

    def test_adhoc_1so_using_default_yml(self):
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Change the admin user
        output = re.sub(r'  admin_user: admin', r'  admin_user: chewbacca', output)
        # Write the default.yml to a file
        os.mkdir(self.DIR)
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[os.path.join(self.FIXTURES_DIR, splunk_container_name) + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("chewbacca", p), "verify": False}
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
                os.remove(os.path.join(self.DIR, "default.yml"))
                os.rmdir(self.DIR)
            except OSError:
                pass

    def test_adhoc_1uf_using_default_yml(self):
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        # Generate default.yml
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Change the admin user
        output = re.sub(r'  admin_user: admin', r'  admin_user: hansolo', output)
        # Write the default.yml to a file
        os.mkdir(self.DIR)
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start", ports=[8089], 
                                            volumes=["/tmp/defaults/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                    port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("hansolo", p), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)
            try:
                os.remove(os.path.join(self.DIR, "default.yml"))
                os.rmdir(self.DIR)
            except OSError:
                pass

    def test_adhoc_1so_splunk_launch_conf(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
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
            splunk_container_name = self.generate_random_string()
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
            splunk_container_name = self.generate_random_string()
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
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/var/secrets/pwfile"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": "/var/secrets/pwfile"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.FIXTURES_DIR + "/pwfile:/var/secrets/pwfile"],
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
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/var/secrets/pwfile"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": "/var/secrets/pwfile"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.FIXTURES_DIR + "/pwfile:/var/secrets/pwfile"],
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
            splunk_container_name = self.generate_random_string()
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
            splunk_container_name = self.generate_random_string()
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
            splunk_container_name = self.generate_random_string()
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

    def test_compose_1so_hec(self):
        # Standup deployment
        self.compose_file_name = "1so_hec.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("so1")
        self.check_common_keys(log_json, "so")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec"]["token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs1("so1")
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
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json1("uf1")
        self.check_common_keys(log_json, "uf")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec"]["token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs1("uf1")
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