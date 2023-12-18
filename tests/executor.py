#!/usr/bin/env python
# encoding: utf-8

import pytest
import time
import os
import sys
import requests
import logging
import docker
import json
import urllib
import yaml
import shlex
import subprocess
import logging.handlers
from shutil import copy
from random import choice
from string import ascii_lowercase
# Code to suppress insecure https warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Define variables
FILE_DIR = os.path.dirname(os.path.normpath(os.path.join(__file__)))
REPO_DIR = os.path.join(FILE_DIR, "..")
# Setup logging
LOGGER = logging.getLogger("docker-splunk")
LOGGER.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(os.path.join(FILE_DIR, "..", "test-results", "docker_splunk_test_python{}.log".format(sys.version_info[0])), maxBytes=25000000)
formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] [%(process)d] %(message)s')
file_handler.setFormatter(formatter)
LOGGER.addHandler(file_handler)
# Define Docker client settings
os.environ['COMPOSE_HTTP_TIMEOUT'] = "500"
os.environ['DOCKER_CLIENT_TIMEOUT'] = "500"


class Executor(object):
    """
    Parent executor class that handles concurrent test execution workflows and shared methods 
    to validate the Docker images for Splunk Enterprise/Universal Forwarder
    """

    logger = LOGGER
    RETRY_COUNT = 3
    RETRY_DELAY = 6 # in seconds

    FIXTURES_DIR = os.path.join(FILE_DIR, "fixtures")
    EXAMPLE_APP = os.path.join(FIXTURES_DIR, "splunk_app_example")
    EXAMPLE_APP_TGZ = os.path.join(FIXTURES_DIR, "splunk_app_example.tgz")
    SCENARIOS_DIR = os.path.join(FILE_DIR, "..", "test_scenarios")
    DEFAULTS_DIR = os.path.join(SCENARIOS_DIR, "defaults")

    @classmethod
    def setup_class(cls, platform):
        cls.client = docker.APIClient()
        # Define images by name to be validated
        cls.BASE_IMAGE_NAME = "base-{}".format(platform)
        cls.SPLUNK_IMAGE_NAME = "splunk-{}".format(platform)
        cls.UF_IMAGE_NAME = "uf-{}".format(platform)
        # Define new, random password for each executor
        cls.password = Executor.generate_random_string()
        cls.compose_file_name = None
        cls.project_name = None
        cls.DIR = None
        cls.container_id = None
        # Wrap into custom env variable for subprocess overrides
        cls.env = {
            "SPLUNK_PASSWORD": cls.password,
            "SPLUNK_IMAGE": cls.SPLUNK_IMAGE_NAME,
            "UF_IMAGE": cls.UF_IMAGE_NAME
        }

    @classmethod
    def teardown_class(cls):
        pass

    @staticmethod
    def generate_random_string():
        return ''.join(choice(ascii_lowercase) for b in range(10))

    def handle_request_retry(self, method, url, kwargs):
        for n in range(Executor.RETRY_COUNT):
            try:
                self.logger.info("Attempt #{}: running {} against {} with kwargs {}".format(n+1, method, url, kwargs))
                resp = requests.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.status_code, resp.content
            except Exception as e:
                self.logger.error("Attempt #{} error: {}".format(n+1, str(e)))
                if n < Executor.RETRY_COUNT-1:
                    time.sleep(Executor.RETRY_DELAY)
                    continue
                raise e

    def get_container_logs(self, container_id):
        stream = self.client.logs(container_id, stream=True)
        output = ""
        for char in stream:
            if "Ansible playbook complete" in char.decode():
                break
            output += char.decode()
        return output

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
        containers = self.client.containers(filters={"label": "com.docker.compose.project={}".format(self.project_name)})
        for container in containers:
            self.client.remove_container(container["Id"], v=True, force=True)
        try:
            self.client.prune_networks({"until": "15s"})
            self.client.prune_volumes()
        except:
            pass

    def wait_for_containers(self, count, label=None, name=None, timeout=500):
        '''
        NOTE: This helper method can only be used for `compose up` scenarios where self.project_name is defined
        '''
        print(f"now WAITING for CONTAINERS to be UP")
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
                    output = self.client.logs(container["Id"], tail=5)
                    if "unable to" in output or "denied" in output or "splunkd.pid file is unreadable" in output:
                        self.logger.error("Container {} did not start properly, last log line: {}".format(container["Names"][0], output))
                        print(f"SCRIPT FAILS TO CREATE CONTAINER")
                        sys.exit(1)
                    elif "Ansible playbook complete" in output:
                        print(f"ANSIBLE EXEC COMPLETE")
                        self.logger.info("Container {} is ready".format(container["Names"][0]))
                        healthy_count += 1
                    else:
                        print(f"IN ELSE WHICH WAS NOT EXPECTED:")
                        print("-------- START LOG ----------")
                        print(output)
                        print("-------- END LOG ----------")
                else:
                    print("ALL GOOD ELSE")
                    self.logger.info("Container {} is ready".format(container["Names"][0]))
                    healthy_count += 1
            if healthy_count == count:
                self.logger.info("All containers ready to proceed")
                break
            print(f"continue for loop without break")
            time.sleep(5)
            end = time.time()
        return True

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

    def compose_up(self, defaults_url=None, apps_url=None):
        container_count = self.get_number_of_containers(os.path.join(self.SCENARIOS_DIR, self.compose_file_name))
        command = "docker compose -p {} -f test_scenarios/{} up -d".format(self.project_name, self.compose_file_name)
        print(f"LOOK AT THIS COMMAND")
        print(command)
        out, err, rc = self._run_command(command, defaults_url, apps_url)
        print("COMPLETED DOCKER COMPOSE")
        print(f"check RC for docker compose: {rc}; check err for docker-compose: {err}")
        print("check output for docker-compose")
        print(out)
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

    def search_internal_distinct_hosts(self, container_id, username="admin", password="password"):
        query = "search index=_internal earliest=-1m | stats dc(host) as distinct_hosts"
        meta, results = self._run_splunk_query(container_id, query, username, password)
        search_providers = meta["entry"][0]["content"]["searchProviders"]
        distinct_hosts = int(results["results"][0]["distinct_hosts"])
        return search_providers, distinct_hosts

    def _run_command(self, command, defaults_url=None, apps_url=None):
        if isinstance(command, list):
            sh = command
        elif isinstance(command, str):
            sh = shlex.split(command)
        self.logger.info("CALL: %s" % sh)
        env = os.environ.copy()
        env["SPLUNK_PASSWORD"] = self.password
        env["SPLUNK_IMAGE"] = self.SPLUNK_IMAGE_NAME
        env["UF_IMAGE"] = self.UF_IMAGE_NAME
        if defaults_url:
            env["SPLUNK_DEFAULTS_URL"] = defaults_url
        if apps_url:
            env["SPLUNK_APPS_URL"] = apps_url
        proc = subprocess.Popen(sh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
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
            assert log_output["all"]["vars"]["ansible_pre_tasks"] == []
            assert log_output["all"]["vars"]["ansible_post_tasks"] == []
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

    def check_dmc(self, containers, num_peers, num_idx, num_sh, num_cm, num_lm):
        for container in containers:
            container_name = container["Names"][0].strip("/")
            splunkd_port = self.client.port(container["Id"], 8089)[0]["HostPort"]
            if container_name == "dmc":
                # check 1: curl -k https://localhost:8089/servicesNS/nobody/splunk_monitoring_console/configs/conf-splunk_monitoring_console_assets/settings?output_mode=json -u admin:helloworld
                status, content = self.handle_request_retry("GET", "https://localhost:{}/servicesNS/nobody/splunk_monitoring_console/configs/conf-splunk_monitoring_console_assets/settings?output_mode=json".format(splunkd_port), 
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                assert output["entry"][0]["content"]["disabled"] == False
                # check 2: curl -k https://localhost:8089/servicesNS/nobody/system/apps/local/splunk_monitoring_console?output_mode=json -u admin:helloworld
                status, content = self.handle_request_retry("GET", "https://localhost:{}/servicesNS/nobody/system/apps/local/splunk_monitoring_console?output_mode=json".format(splunkd_port), 
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                assert output["entry"][0]["content"]["disabled"] == False
                # check 3: curl -k https://localhost:8089/services/search/distributed/peers?output_mode=json -u admin:helloworld
                status, content = self.handle_request_retry("GET", "https://localhost:{}/services/search/distributed/peers?output_mode=json".format(splunkd_port),
                                                            {"auth": ("admin", self.password), "verify": False})
                assert status == 200
                output = json.loads(content)
                assert num_peers == len(output["entry"])
                for peer in output["entry"]:
                    assert peer["content"]["status"] == "Up"
                self.check_dmc_groups(splunkd_port, num_idx, num_sh, num_cm, num_lm)

    def check_dmc_groups(self, splunkd_port, num_idx, num_sh, num_cm, num_lm):
        # check dmc_group_indexer
        status, content = self.handle_request_retry("GET", "https://localhost:{}/services/search/distributed/groups/dmc_group_indexer?output_mode=json".format(splunkd_port), 
                                                    {"auth": ("admin", self.password), "verify": False})
        assert status == 200
        output = json.loads(content)
        assert len(output["entry"][0]["content"]["member"]) == num_idx
        # check dmc_group_cluster_master
        status, content = self.handle_request_retry("GET", "https://localhost:{}/services/search/distributed/groups/dmc_group_cluster_master?output_mode=json".format(splunkd_port), 
                                                    {"auth": ("admin", self.password), "verify": False})
        assert status == 200
        output = json.loads(content)
        assert len(output["entry"][0]["content"]["member"]) == num_cm
        # check dmc_group_license_master
        status, content = self.handle_request_retry("GET", "https://localhost:{}/services/search/distributed/groups/dmc_group_license_master?output_mode=json".format(splunkd_port), 
                                                    {"auth": ("admin", self.password), "verify": False})
        assert status == 200
        output = json.loads(content)
        assert len(output["entry"][0]["content"]["member"]) == num_lm
        # check dmc_group_search_head
        status, content = self.handle_request_retry("GET", "https://localhost:{}/services/search/distributed/groups/dmc_group_search_head?output_mode=json".format(splunkd_port), 
                                                    {"auth": ("admin", self.password), "verify": False})
        assert status == 200
        output = json.loads(content)
        assert len(output["entry"][0]["content"]["member"]) == num_sh
