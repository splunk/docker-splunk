#!/usr/bin/env python
# encoding: utf-8

import os
import time
import shlex
import pytest
import docker
from docker.types import Mount
import requests
import subprocess
import tarfile
import logging
import logging.handlers
import sys
from random import choice
from string import ascii_lowercase
# Code to suppress insecure https warnings
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)


# Define variables
FILE_DIR = os.path.dirname(os.path.normpath(os.path.join(__file__)))
REPO_DIR = os.path.join(FILE_DIR, "..")
# Setup logging
LOGGER = logging.getLogger("docker-splunk")
LOGGER.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(os.path.join(FILE_DIR, "docker_splunk_test_python{}.log".format(sys.version_info[0])), maxBytes=25000000)
formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] [%(process)d] %(message)s')
file_handler.setFormatter(formatter)
LOGGER.addHandler(file_handler)


class Executor(object):
    """
    Parent executor class that handles concurrent test execution workflows and shared methods 
    to validate the Docker images for Splunk Enterprise/Universal Forwarder
    """

    logger = LOGGER
    RETRY_COUNT = 3
    RETRY_DELAY = 6 # in seconds

    @classmethod
    def setup_class(cls, platform):
        cls.client = docker.APIClient()
        # Define images by name to be validated
        cls.BASE_IMAGE_NAME = "base-{}".format(platform)
        cls.SPLUNK_IMAGE_NAME = "splunk-{}".format(platform)
        cls.UF_IMAGE_NAME = "uf-{}".format(platform)
        # Define new, random password for each executor
        cls.password = Executor.generate_random_string()
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

    @classmethod
    def _run_cmd(cls, cmd, cwd=REPO_DIR):
        if isinstance(cmd, list):
            sh = command
        elif isinstance(command, str):
            sh = shlex.split(command)
        cls.logger.info("CALL: {}".format(sh))
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
        self.logger.info("STDOUT: {}".format(out))
        err = "".join(err_lines)
        self.logger.info("STDERR: {}".format(err))
        self.logger.info("RC: {}".format(proc.returncode))
        return out, err, proc.returncode

    def handle_request_retry(self, method, url, kwargs):
        for n in range(Executor.RETRY_COUNT):
            try:
                self.logger.info("Attempt #{}: running {} against {} with kwargs {}".format(n+1, method, url, kwargs))
                resp = requests.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
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
            if "Ansible playbook complete" in char:
                break
            output += char
        return output

    def get_container_logs1(self, container_id):
        container_id = "{}_{}_1".format(self.project_name, container_id)
        stream = self.client.logs(container_id, stream=True)
        output = ""
        for char in stream:
            if "Ansible playbook complete" in char:
                break
            output += char
        return output
