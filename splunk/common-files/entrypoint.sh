#!/bin/bash
# Copyright 2018-2021 Splunk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

setup() {
	# Check if the user accepted the license
	if [[ "$SPLUNK_START_ARGS" != *"--accept-license"* ]]; then
		printf "License not accepted, please ensure the environment variable SPLUNK_START_ARGS contains the '--accept-license' flag\n"
		printf "For example: docker run -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD splunk/splunk\n\n"
		printf "For additional information and examples, see the help: docker run -it splunk/splunk help\n"
		exit 1
	fi
}

teardown() {
	# Always run the stop command on termination
	if [ `whoami` != "${SPLUNK_USER}" ]; then
		RUN_AS_SPLUNK="sudo -u ${SPLUNK_USER}"
	fi
	${RUN_AS_SPLUNK} ${SPLUNK_HOME}/bin/splunk stop || true
}

trap teardown SIGINT SIGTERM

prep_ansible() {
	cd ${SPLUNK_ANSIBLE_HOME}
	if [ `whoami` == "${SPLUNK_USER}" ]; then
		sed -i -e "s,^become\\s*=.*,become = false," ansible.cfg
	fi
	if [[ "$DEBUG" == "true" ]]; then
		ansible-playbook --version
		python inventory/environ.py --write-to-file
		cat /opt/container_artifact/ansible_inventory.json 2>/dev/null
		cat /opt/ansible/inventory/messages.txt 2>/dev/null || true
		echo
	fi
}

watch_for_failure(){
	if [[ $? -eq 0 ]]; then
		sh -c "echo 'started' > ${CONTAINER_ARTIFACT_DIR}/splunk-container.state"
	fi
	echo ===============================================================================
	echo
	user_permission_change
	if [ `whoami` != "${SPLUNK_USER}" ]; then
		RUN_AS_SPLUNK="sudo -u ${SPLUNK_USER}"
	fi
	# Any crashes/errors while Splunk is running should get logged to splunkd_stderr.log and sent to the container's stdout
	if [ -z "$SPLUNK_TAIL_FILE" ]; then
		echo Ansible playbook complete, will begin streaming splunkd_stderr.log
		${RUN_AS_SPLUNK} tail -n 0 -f ${SPLUNK_HOME}/var/log/splunk/splunkd_stderr.log &
	else
		echo Ansible playbook complete, will begin streaming ${SPLUNK_TAIL_FILE}
		${RUN_AS_SPLUNK} tail -n 0 -f ${SPLUNK_TAIL_FILE} &
	fi
	wait
}

create_defaults() {
	createdefaults.py
}

start_and_exit() {
	if [ -z "$SPLUNK_PASSWORD" ]
	then
		echo "WARNING: No password ENV var.  Stack may fail to provision if splunk.password is not set in ENV or a default.yml"
	fi
	sh -c "echo 'starting' > ${CONTAINER_ARTIFACT_DIR}/splunk-container.state"
	setup
	prep_ansible
	ansible-playbook $ANSIBLE_EXTRA_FLAGS -i inventory/environ.py -l localhost site.yml
}

start() {
	start_and_exit
	watch_for_failure
}

configure_multisite() {
	prep_ansible
	ansible-playbook $ANSIBLE_EXTRA_FLAGS -i inventory/environ.py -l localhost multisite.yml
}

restart(){
	sh -c "echo 'restarting' > ${CONTAINER_ARTIFACT_DIR}/splunk-container.state"
	prep_ansible
	${SPLUNK_HOME}/bin/splunk stop 2>/dev/null || true
	ansible-playbook -i inventory/environ.py -l localhost start.yml
	watch_for_failure
}

user_permission_change(){
	if [[ "$STEPDOWN_ANSIBLE_USER" == "true" ]]; then
		bash -c "sudo deluser -q ansible sudo"
	fi
}

help() {
	cat << EOF
  ____        _             _      __
 / ___| _ __ | |_   _ _ __ | | __  \ \\
 \___ \| '_ \| | | | | '_ \| |/ /   \ \\
  ___) | |_) | | |_| | | | |   <    / /
 |____/| .__/|_|\__,_|_| |_|_|\_\  /_/
       |_|
========================================

Environment Variables:
  * SPLUNK_USER - user under which to run Splunk (default: splunk)
  * SPLUNK_GROUP - group under which to run Splunk (default: splunk)
  * SPLUNK_HOME - home directory where Splunk gets installed (default: /opt/splunk)
  * SPLUNK_START_ARGS - arguments to pass into the Splunk start command; you must include '--accept-license' to start Splunk (default: none)
  * SPLUNK_PASSWORD - password to log into this Splunk instance, you must include a password (default: none)
  * SPLUNK_ROLE - the role of this Splunk instance (default: splunk_standalone)
      Acceptable values:
        - splunk_standalone
        - splunk_search_head
        - splunk_indexer
        - splunk_deployer
        - splunk_license_master
        - splunk_cluster_master
        - splunk_heavy_forwarder
  * SPLUNK_LICENSE_URI - URI or local file path (absolute path in the container) to a Splunk license
  * SPLUNK_STANDALONE_URL, SPLUNK_INDEXER_URL, ... - comma-separated list of resolvable aliases to properly bring-up a distributed environment.
                                                     This is optional for standalones, but required for multi-node Splunk deployments.
  * SPLUNK_BUILD_URL - URL to a Splunk build which will be installed (instead of the image's default build)
  * SPLUNK_APPS_URL - comma-separated list of URLs to Splunk apps which will be downloaded and installed

Examples:
  * docker run -it -e SPLUNK_PASSWORD=helloworld -p 8000:8000 splunk/splunk start
  * docker run -it -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD=helloworld -p 8000:8000 -p 8089:8089 splunk/splunk start
  * docker run -it -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_LICENSE_URI=http://example.com/splunk.lic -e SPLUNK_PASSWORD=helloworld -p 8000:8000 splunk/splunk start
  * docker run -it -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_INDEXER_URL=idx1,idx2 -e SPLUNK_SEARCH_HEAD_URL=sh1,sh2 -e SPLUNK_ROLE=splunk_search_head --hostname sh1 --network splunknet --network-alias sh1 -e SPLUNK_PASSWORD=helloworld -e SPLUNK_LICENSE_URI=http://example.com/splunk.lic splunk/splunk start

EOF
	exit 1
}

case "$1" in
	start|start-service)
		shift
		start $@
		;;
	start-and-exit)
		shift
		start_and_exit $@
		;;
	configure-multisite)
		shift
		configure_multisite $0
		;;
	create-defaults)
		create_defaults
		;;
	restart)
		shift
		restart $@
		;;
	no-provision)
		user_permission_change
		tail -n 0 -f /etc/hosts &
		wait
		;;
	bash|splunk-bash)
		/bin/bash --init-file ${SPLUNK_HOME}/bin/setSplunkEnv
		;;
	help)
		shift
		help $@
		;;
	*)
		shift
		help $@
		;;
esac


