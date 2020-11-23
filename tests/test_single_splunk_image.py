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

    def test_splunk_entrypoint_help(self):
        # Run container
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="help")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        assert "SPLUNK_HOME - home directory where Splunk gets installed (default: /opt/splunk)" in output
        assert "Examples:" in output
    
    def test_splunk_scloud(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the version returns successfully for multiple users
            for user in ["splunk", "ansible"]:
                exec_command = self.client.exec_create(cid, "scloud version", user=user)
                std_out = self.client.exec_start(exec_command)
                assert "scloud version " in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_splunk_ulimit(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that nproc limits are unlimited
            exec_command = self.client.exec_create(cid, "sudo -u splunk bash -c 'ulimit -u'")
            std_out = self.client.exec_start(exec_command)
            assert "unlimited" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

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

    def test_compose_1so_trial(self):
        # Standup deployment
        self.compose_file_name = "1so_trial.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
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
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
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
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
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
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("admin2", "changemepls")
        assert self.check_splunkd("admin3", "changemepls")
    
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
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("newman", "changemepls")

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
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec"]["token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
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

    def test_adhoc_1so_preplaybook_with_sudo(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_PRE_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.FIXTURES_DIR + "/sudo_touch_dummy_file.yml:/playbooks/play.yml"],
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
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_POST_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.FIXTURES_DIR + "/touch_dummy_file.yml:/playbooks/play.yml"],
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
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_POST_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.FIXTURES_DIR + "/sudo_touch_dummy_file.yml:/playbooks/play.yml"],
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
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        DIR_EXAMPLE_APP = os.path.join(self.DIR, "splunk_app_example")
        copytree(self.EXAMPLE_APP, DIR_EXAMPLE_APP)
        self.EXAMPLE_APP_TGZ = os.path.join(self.DIR, "splunk_app_example.tgz")
        with tarfile.open(self.EXAMPLE_APP_TGZ, "w:gz") as tar:
            tar.add(DIR_EXAMPLE_APP, arcname=os.path.basename(DIR_EXAMPLE_APP))
        # Generate default.yml
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Change repl factor & search factor
        output = re.sub(r'  user: splunk', r'  user: splunk\n  apps_location: /tmp/defaults/splunk_app_example.tgz', output)
        # Write the default.yml to a file
        # os.mkdir(self.DIR)
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
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
            kwargs = {"auth": ("admin", p), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check the app endpoint
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", p), "verify": False}
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
                os.remove(self.EXAMPLE_APP_TGZ)
                os.remove(os.path.join(self.DIR, "default.yml"))
            except OSError:
                pass

    def test_adhoc_1so_bind_mount_apps(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        DIR_EXAMPLE_APP = os.path.join(self.DIR, "splunk_app_example")
        copytree(self.EXAMPLE_APP, DIR_EXAMPLE_APP)
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Write the default.yml to a file
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
                                            volumes=["/tmp/defaults/", "/opt/splunk/etc/apps/splunk_app_example/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/", 
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
            kwargs = {"auth": ("admin", p), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
            # Check the app endpoint
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", p), "verify": False}
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
                os.remove(os.path.join(self.DIR, "default.yml"))
            except OSError:
                pass

    def test_adhoc_1so_run_as_root(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
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
     

    def test_adhoc_1so_declarative_password(self):
        """
        This test is intended to check how the container gets provisioned with declarative passwords
        """
        # Create a splunk container
        cid = None
        try:
            # Start the container using no-provision, otherwise we can't mutate the password
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            name=splunk_container_name,
                                            command="no-provision",
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_DECLARATIVE_ADMIN_PASSWORD": "true"
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Create a new /tmp/defaults/default.yml to change desired HEC settings
            exec_command = self.client.exec_create(cid, "mkdir -p /tmp/defaults", user="splunk")
            self.client.exec_start(exec_command)
            exec_command = self.client.exec_create(cid, "touch /tmp/defaults/default.yml", user="splunk")
            self.client.exec_start(exec_command)
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  password: thisisarealpassword123
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Execute ansible
            exec_command = self.client.exec_create(cid, "/sbin/entrypoint.sh start-and-exit")
            std_out = self.client.exec_start(exec_command)
            # Check splunk with the initial password
            assert self.check_splunkd("admin", "thisisarealpassword123", name=splunk_container_name)
            # Mutate the password so that ansible changes it on the next run
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  password: thisisadifferentpw456
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Execute ansible again
            exec_command = self.client.exec_create(cid, "/sbin/entrypoint.sh start-and-exit")
            stdout = self.client.exec_start(exec_command)
            # Check splunk with the initial password
            assert self.check_splunkd("admin", "thisisadifferentpw456", name=splunk_container_name)
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1uf_declarative_password(self):
        """
        This test is intended to check how the container gets provisioned with declarative passwords
        """
        # Create a splunk container
        cid = None
        try:
            # Start the container using no-provision, otherwise we can't mutate the password
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8089], 
                                            name=splunk_container_name,
                                            command="no-provision",
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_DECLARATIVE_ADMIN_PASSWORD": "true"
                                                        },
                                            host_config=self.client.create_host_config(port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Create a new /tmp/defaults/default.yml to change desired HEC settings
            exec_command = self.client.exec_create(cid, "mkdir -p /tmp/defaults", user="splunk")
            self.client.exec_start(exec_command)
            exec_command = self.client.exec_create(cid, "touch /tmp/defaults/default.yml", user="splunk")
            self.client.exec_start(exec_command)
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  password: thisisarealpassword123
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Execute ansible
            exec_command = self.client.exec_create(cid, "/sbin/entrypoint.sh start-and-exit")
            std_out = self.client.exec_start(exec_command)
            # Check splunk with the initial password
            assert self.check_splunkd("admin", "thisisarealpassword123", name=splunk_container_name)
            # Mutate the password so that ansible changes it on the next run
            exec_command = self.client.exec_create(cid, '''bash -c 'cat > /tmp/defaults/default.yml << EOL 
splunk:
  password: thisisadifferentpw456
EOL'
''', user="splunk")
            self.client.exec_start(exec_command)
            # Execute ansible again
            exec_command = self.client.exec_create(cid, "/sbin/entrypoint.sh start-and-exit")
            stdout = self.client.exec_start(exec_command)
            # Check splunk with the initial password
            assert self.check_splunkd("admin", "thisisadifferentpw456", name=splunk_container_name)
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
            splunk_container_name = self.generate_random_string()
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
            exec_command = self.client.exec_create(cid, "touch /tmp/defaults/default.yml", user="splunk")
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
            splunk_container_name = self.generate_random_string()
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Update server ssl settings
        output = re.sub(r'''^  ssl:.*?password: null''', r'''  ssl:
    ca: null
    cert: null
    enable: false
    password: null''', output, flags=re.MULTILINE|re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_CERT_PREFIX": "http",
                                                            "SPLUNK_PASSWORD": p},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", p, name=splunk_container_name, scheme="http")
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "enableSplunkdSSL = false" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "http://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", p)}
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
            except OSError:
                pass

    def test_adhoc_1so_web_ssl(self):
        # Create the container
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
        cid = None
        try:
            # Commands to generate self-signed certificates for SplunkWeb here: https://docs.splunk.com/Documentation/Splunk/latest/Security/Self-signcertificatesforSplunkWeb
            cmd = "openssl req -x509 -newkey rsa:4096 -passout pass:abcd1234 -keyout {path}/key.pem -out {path}/cert.pem -days 365 -subj /CN=localhost".format(path=self.DIR)
            generate_certs = subprocess.check_output(cmd.split())
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_HTTP_ENABLESSL": "true",
                                                            "SPLUNK_HTTP_ENABLESSL_CERT": "/tmp/defaults/cert.pem",
                                                            "SPLUNK_HTTP_ENABLESSL_PRIVKEY": "/tmp/defaults/key.pem",
                                                            "SPLUNK_HTTP_ENABLESSL_PRIVKEY_PASSWORD": "abcd1234"
                                                            },
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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
                os.remove(os.path.join(self.DIR, "key.pem"))
                os.remove(os.path.join(self.DIR, "cert.pem"))
            except OSError:
                pass
 
    def test_compose_1so_java_oracle(self):
        # Standup deployment
        self.compose_file_name = "1so_java_oracle.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "oracle:8"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if java is installed
        exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "java version \"1.8.0" in std_out
        # Restart the container and make sure java is still installed
        self.client.restart("{}_so1_1".format(self.project_name))
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        assert self.check_splunkd("admin", self.password)
        exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "java version \"1.8.0" in std_out
 

    def test_compose_1so_java_openjdk8(self):
        # Standup deployment
        self.compose_file_name = "1so_java_openjdk8.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "openjdk:8"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if java is installed
        exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"1.8.0" in std_out
        # Restart the container and make sure java is still installed
        self.client.restart("{}_so1_1".format(self.project_name))
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        assert self.check_splunkd("admin", self.password)
        exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"1.8.0" in std_out
 

    def test_compose_1so_java_openjdk11(self):
        # Standup deployment
        self.compose_file_name = "1so_java_openjdk11.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["java_version"] == "openjdk:11"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if java is installed
        exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"11.0.2" in std_out
        # Restart the container and make sure java is still installed
        self.client.restart("{}_so1_1".format(self.project_name))
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        assert self.check_splunkd("admin", self.password)
        exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "java -version")
        std_out = self.client.exec_start(exec_command)
        assert "openjdk version \"11.0.2" in std_out

    def test_compose_1so_enable_service(self):
        # Standup deployment
        self.compose_file_name = "1so_enable_service.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        try:
            # enable_service is set in the compose file
            assert log_json["all"]["vars"]["splunk"]["enable_service"] == "true"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if service is registered
        if 'debian' in PLATFORM:
            exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "sudo service splunk status")
            std_out = self.client.exec_start(exec_command)
            assert "splunkd is running" in std_out
        else:
            exec_command = self.client.exec_create("{}_so1_1".format(self.project_name), "stat /etc/init.d/splunk")
            std_out = self.client.exec_start(exec_command)
            assert "/etc/init.d/splunk" in std_out
 
    def test_adhoc_1so_hec_custom_cert(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
        cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "glootie"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            password = "helloworld"
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8088, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, name=splunk_container_name)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[http://splunk_hec_token]" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            assert "sslPassword = " in std_out
            # Check HEC using the custom certs
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "https://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk doyouwannadevelopanapp"}, "verify": "{}/cacert.pem".format(self.DIR)}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
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

    def test_adhoc_1so_splunktcp_ssl(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
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
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, name=splunk_container_name)
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
            try:
                os.remove(os.path.join(self.DIR, "default.yml"))
            except OSError:
                pass

    def test_adhoc_1so_splunkd_custom_ssl(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
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
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, name=splunk_container_name)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunk/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "sslRootCAPath = /tmp/defaults/ca.pem" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", password), "verify": "{}/cacert.pem".format(self.DIR)}
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
            except OSError:
                pass
     
    def test_adhoc_1so_upgrade(self):
        # Pull the old image
        for line in self.client.pull("splunk/splunk:{}".format(OLD_SPLUNK_VERSION), stream=True, decode=True):
            continue
        # Create the "splunk-old" container
        try:
            cid = None
            splunk_container_name = self.generate_random_string()
            user, password = "admin", self.generate_random_string()
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
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name), "name": splunk_container_name})
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
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
            splunk_container_name = self.generate_random_string()
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
            containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name), "name": splunk_container_name})
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(splunkd_port)
            kwargs = {"auth": ("admin", password), "verify": False}
            status, content = self.handle_request_retry("GET", url, kwargs)
            assert status == 200
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

    def test_adhoc_1so_preplaybook(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, ports=[8089], 
                                            volumes=["/playbooks/play.yml"], name=splunk_container_name,
                                            environment={
                                                            "DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": self.password,
                                                            "SPLUNK_ANSIBLE_PRE_TASKS": "file:///playbooks/play.yml"
                                                        },
                                            host_config=self.client.create_host_config(binds=[self.FIXTURES_DIR + "/touch_dummy_file.yml:/playbooks/play.yml"],
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

    def test_compose_1so_apps(self):
        self.project_name = self.generate_random_string()
        # Tar the app before spinning up the scenario
        with tarfile.open(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)), "w:gz") as tar:
            tar.add(self.EXAMPLE_APP, arcname=os.path.basename(self.EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1so_apps.yaml"
        container_count, rc = self.compose_up(apps_url="http://appserver/{}.tgz".format(self.project_name))
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_so1_1".format(self.project_name))
        self.check_common_keys(log_json, "so")
        try:
            assert log_json["all"]["vars"]["splunk"]["apps_location"][0] == "http://appserver/{}.tgz".format(self.project_name)
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["default"] == "/opt/splunk/etc/apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["deployment"] == "/opt/splunk/etc/deployment-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["httpinput"] == "/opt/splunk/etc/apps/splunk_httpinput"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["idxc"] == "/opt/splunk/etc/master-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["shc"] == "/opt/splunk/etc/shcluster/apps"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_so1_1".format(self.project_name))
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
            os.remove(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)))
        except OSError:
            pass

    def test_adhoc_1so_custom_conf(self):
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.SPLUNK_IMAGE_NAME, tty=True, command="start", ports=[8089], 
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
                os.remove(os.path.join(self.DIR, "default.yml"))
                rmtree(self.DIR)
            except OSError:
                pass

    def test_compose_1uf_apps(self):
        self.project_name = self.generate_random_string()
         # Tar the app before spinning up the scenario
        with tarfile.open(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)), "w:gz") as tar:
            tar.add(self.EXAMPLE_APP, arcname=os.path.basename(self.EXAMPLE_APP))
        # Standup deployment
        self.compose_file_name = "1uf_apps.yaml"
        container_count, rc = self.compose_up(apps_url="http://appserver/{}.tgz".format(self.project_name))
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_uf1_1".format(self.project_name))
        self.check_common_keys(log_json, "uf")
        try:
            assert log_json["all"]["vars"]["splunk"]["apps_location"][0] == "http://appserver/{}.tgz".format(self.project_name)
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["default"] == "/opt/splunkforwarder/etc/apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["deployment"] == "/opt/splunkforwarder/etc/deployment-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["httpinput"] == "/opt/splunkforwarder/etc/apps/splunk_httpinput"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["idxc"] == "/opt/splunkforwarder/etc/master-apps"
            assert log_json["all"]["vars"]["splunk"]["app_paths"]["shc"] == "/opt/splunkforwarder/etc/shcluster/apps"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_uf1_1".format(self.project_name))
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
            os.remove(os.path.join(self.FIXTURES_DIR, "{}.tgz".format(self.project_name)))
        except OSError:
            pass

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

    def test_adhoc_1uf_splunktcp_ssl(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
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
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, name=splunk_container_name)
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
            try:
                os.remove(os.path.join(self.DIR, "default.yml"))
            except OSError:
                pass

    def test_adhoc_1uf_splunkd_custom_ssl(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
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
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "sslRootCAPath = /tmp/defaults/ca.pem" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", password), "verify": "{}/cacert.pem".format(self.DIR)}
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
            except OSError:
                pass

    def test_adhoc_1uf_hec_custom_cert(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Commands to generate self-signed certificates for Splunk here: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates
        passphrase = "glootie"
        cmds = [    
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/ca.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -key {path}/ca.key -passin pass:{pw} -out {path}/ca.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -in {path}/ca.csr -sha512 -passin pass:{pw} -signkey {path}/ca.key -CAcreateserial -out {path}/ca.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "openssl genrsa -aes256 -passout pass:{pw} -out {path}/server.key 2048".format(pw=passphrase, path=self.DIR),
                    "openssl req -new -passin pass:{pw} -key {path}/server.key -out {path}/server.csr -subj /CN=localhost".format(pw=passphrase, path=self.DIR),
                    "openssl x509 -req -passin pass:{pw} -in {path}/server.csr -SHA256 -CA {path}/ca.pem -CAkey {path}/ca.key -CAcreateserial -out {path}/server.pem -days 3".format(pw=passphrase, path=self.DIR),
                    "cat {path}/server.pem {path}/server.key {path}/ca.pem > {path}/cert.pem".format(path=self.DIR),
                    "cat {path}/server.pem {path}/ca.pem > {path}/cacert.pem".format(path=self.DIR)
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
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            password = "helloworld"
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8088, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_PASSWORD": password},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8088: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", password, name=splunk_container_name)
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/apps/splunk_httpinput/local/inputs.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "[http://splunk_hec_token]" in std_out
            assert "serverCert = /tmp/defaults/cert.pem" in std_out
            assert "sslPassword = " in std_out
            # Check HEC using the custom certs
            hec_port = self.client.port(cid, 8088)[0]["HostPort"]
            url = "https://localhost:{}/services/collector/event".format(hec_port)
            kwargs = {"json": {"event": "hello world"}, "headers": {"Authorization": "Splunk doyouwannadevelopanapp"}, "verify": "{}/cacert.pem".format(self.DIR)}
            status, content = self.handle_request_retry("POST", url, kwargs)
            assert status == 200
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

    def test_compose_1uf_enable_service(self):
        # Standup deployment
        self.compose_file_name = "1uf_enable_service.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_uf1_1".format(self.project_name))
        self.check_common_keys(log_json, "uf")
        try:
            # enable_service is set in the compose file
            assert log_json["all"]["vars"]["splunk"]["enable_service"] == "true"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_uf1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check if service is registered
        if 'debian' in PLATFORM:
            exec_command = self.client.exec_create("{}_uf1_1".format(self.project_name), "sudo service splunk status")
            std_out = self.client.exec_start(exec_command)
            assert "splunkd is running" in std_out
        else:
            exec_command = self.client.exec_create("{}_uf1_1".format(self.project_name), "stat /etc/init.d/splunk")
            std_out = self.client.exec_start(exec_command)
            assert "/etc/init.d/splunk" in std_out

    def test_adhoc_1uf_splunkd_no_ssl(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Update server ssl settings
        output = re.sub(r'''^  ssl:.*?password: null''', r'''  ssl:
    ca: null
    cert: null
    enable: false
    password: null''', output, flags=re.MULTILINE|re.DOTALL)
        # Write the default.yml to a file
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, ports=[8000, 8089], 
                                               volumes=["/tmp/defaults/"], name=splunk_container_name,
                                               environment={"DEBUG": "true", 
                                                            "SPLUNK_START_ARGS": "--accept-license",
                                                            "SPLUNK_CERT_PREFIX": "http",
                                                            "SPLUNK_PASSWORD": p},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/"],
                                                                                       port_bindings={8089: ("0.0.0.0",), 8000: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", p, name=splunk_container_name, scheme="http")
            # Check if the created file exists
            exec_command = self.client.exec_create(cid, "cat /opt/splunkforwarder/etc/system/local/server.conf", user="splunk")
            std_out = self.client.exec_start(exec_command)
            assert "enableSplunkdSSL = false" in std_out
            # Check splunkd using the custom certs
            mgmt_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "http://localhost:{}/services/server/info".format(mgmt_port)
            kwargs = {"auth": ("admin", p)}
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
            except OSError:
                pass

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
        log_json = self.extract_json("{}_uf1_1".format(self.project_name))
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("{}_uf1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("normalplebe", "newpassword")

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
        log_json = self.extract_json("{}_uf1_1".format(self.project_name))
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("{}_uf1_1".format(self.project_name))
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
        log_json = self.extract_json("{}_uf1_1".format(self.project_name))
        self.check_common_keys(log_json, "uf")
        # Check container logs
        output = self.get_container_logs("{}_uf1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("jerry", "changemepls")
        assert self.check_splunkd("george", "changemepls")

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

    def test_adhoc_1uf_hec_ssl_disabled(self):
        # Create the container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
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
            assert self.check_splunkd("admin", self.password, name=splunk_container_name)
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

    def test_compose_1uf_hec(self):
        # Standup deployment
        self.compose_file_name = "1uf_hec.yaml"
        self.project_name = self.generate_random_string()
        container_count, rc = self.compose_up()
        assert rc == 0
        # Wait for containers to come up
        assert self.wait_for_containers(container_count, label="com.docker.compose.project={}".format(self.project_name))
        # Check ansible inventory json
        log_json = self.extract_json("{}_uf1_1".format(self.project_name))
        self.check_common_keys(log_json, "uf")
        try:
            # token "abcd1234" is hard-coded within the 1so_hec.yaml compose
            assert log_json["all"]["vars"]["splunk"]["hec"]["token"] == "abcd1234"
        except KeyError as e:
            self.logger.error(e)
            raise e
        # Check container logs
        output = self.get_container_logs("{}_uf1_1".format(self.project_name))
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

    def test_adhoc_1uf_splunk_pass4symmkey(self):
        # Create a splunk container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
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
            splunk_container_name = self.generate_random_string()
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

    def test_adhoc_1uf_bind_mount_apps(self):
        # Generate default.yml
        splunk_container_name = self.generate_random_string()
        self.project_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        DIR_EXAMPLE_APP = os.path.join(self.DIR, "splunk_app_example")
        copytree(self.EXAMPLE_APP, DIR_EXAMPLE_APP)
        cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="create-defaults")
        self.client.start(cid.get("Id"))
        output = self.get_container_logs(cid.get("Id"))
        self.client.remove_container(cid.get("Id"), v=True, force=True)
        # Get the password
        p = re.search(r"^  password: (.*?)\n", output, flags=re.MULTILINE|re.DOTALL).group(1).strip()
        assert p and p != "null"
        # Write the default.yml to a file
        with open(os.path.join(self.DIR, "default.yml"), "w") as f:
            f.write(output)
        # Create the container and mount the default.yml
        cid = None
        try:
            # Spin up this container, but also bind-mount the app in the fixtures directory
            splunk_container_name = self.generate_random_string()
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="start-service", ports=[8089], 
                                            volumes=["/tmp/defaults/", "/opt/splunkforwarder/etc/apps/splunk_app_example/"], name=splunk_container_name,
                                            environment={"DEBUG": "true", "SPLUNK_START_ARGS": "--accept-license"},
                                            host_config=self.client.create_host_config(binds=[self.DIR + ":/tmp/defaults/", 
                                                                                              DIR_EXAMPLE_APP + ":/opt/splunkforwarder/etc/apps/splunk_app_example/"],
                                                                                       port_bindings={8089: ("0.0.0.0",)})
                                            )
            cid = cid.get("Id")
            self.client.start(cid)
            # Poll for the container to be ready
            assert self.wait_for_containers(1, name=splunk_container_name)
            # Check splunkd
            assert self.check_splunkd("admin", p, name=splunk_container_name)
            # Check the app endpoint
            splunkd_port = self.client.port(cid, 8089)[0]["HostPort"]
            url = "https://localhost:{}/servicesNS/nobody/splunk_app_example/configs/conf-app/launcher?output_mode=json".format(splunkd_port)
            kwargs = {"auth": ("admin", p), "verify": False}
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
                os.remove(os.path.join(self.DIR, "default.yml"))
            except OSError:
                pass

    def test_uf_scloud(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that the version returns successfully for multiple users
            for user in ["splunk", "ansible"]:
                exec_command = self.client.exec_create(cid, "scloud version", user=user)
                std_out = self.client.exec_start(exec_command)
                assert "scloud version " in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_uf_ulimit(self):
        cid = None
        try:
            # Run container
            cid = self.client.create_container(self.UF_IMAGE_NAME, tty=True, command="no-provision")
            cid = cid.get("Id")
            self.client.start(cid)
            # Wait a bit
            time.sleep(5)
            # If the container is still running, we should be able to exec inside
            # Check that nproc limits are unlimited
            exec_command = self.client.exec_create(cid, "sudo -u splunk bash -c 'ulimit -u'")
            std_out = self.client.exec_start(exec_command)
            assert "unlimited" in std_out
        except Exception as e:
            self.logger.error(e)
            raise e
        finally:
            if cid:
                self.client.remove_container(cid, v=True, force=True)

    def test_adhoc_1uf_custom_conf(self):
        splunk_container_name = self.generate_random_string()
        self.DIR = os.path.join(self.FIXTURES_DIR, splunk_container_name)
        os.mkdir(self.DIR)
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
                os.remove(os.path.join(self.DIR, "default.yml"))
                rmtree(self.DIR)
            except OSError:
                pass

    def test_adhoc_1uf_run_as_root(self):
        # Create a uf container
        cid = None
        try:
            splunk_container_name = self.generate_random_string()
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
        log_json = self.extract_json("{}_hf1_1".format(self.project_name))
        self.check_common_keys(log_json, "hf")
        # Check container logs
        output = self.get_container_logs("{}_hf1_1".format(self.project_name))
        self.check_ansible(output)
        # Check Splunkd on all the containers
        assert self.check_splunkd("admin", self.password)
        # Check Splunkd using the new users
        assert self.check_splunkd("jerry", "seinfeld")