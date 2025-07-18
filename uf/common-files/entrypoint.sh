#!/bin/bash

# Copyright 2018-2025 Splunk
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
	if [[ "$SPLUNK_GENERAL_TERMS" != *"--accept-sgt-current-at-splunk-com"* ]] || [[ "$SPLUNK_START_ARGS" != *"--accept-license"* ]]; then
		printf "License not accepted, please adjust SPLUNK_GENERAL_TERMS and/or SPLUNK_START_ARGS to indicate you have accepted the current/latest version of the license.\n"
		printf "The license you are accepting is the Splunk General Terms, available here: https://www.splunk.com/en_us/legal/splunk-general-terms.html, as may be updated from time to time.\n"
		printf "Unless you have jointly executed with Splunk a negotiated version of these General Terms that explicitly supersedes this agreement, by accessing or using Splunk software, you are agreeing to the Splunk General Terms posted at the time of your access and use.\n"
		printf "Please read and make sure you agree to the Splunk General Terms before you access or use this software.\n"
		printf "Only once you've done so should you include the '--accept-sgt-current-at-splunk-com' and '--accept-license' flags to indicate your acceptance of the Splunk General Terms and launch this software.\n"
		printf "For example: docker run -e SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD splunk/splunk\n\n"
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
		echo
	fi
}

watch_for_failure(){
	if [[ $? -eq 0 ]]; then
		sh -c "echo 'started' > ${CONTAINER_ARTIFACT_DIR}/splunk-container.state"
	fi
	echo ===============================================================================
	echo
	echo Ansible playbook complete, will begin streaming var/log/splunk/splunkd_stderr.log
	echo
	user_permission_change
	if [ `whoami` != "${SPLUNK_USER}" ]; then
		RUN_AS_SPLUNK="sudo -u ${SPLUNK_USER}"
	fi
	# Any crashes/errors while Splunk is running should get logged to splunkd_stderr.log and sent to the container's stdout
	if [ -z "$SPLUNK_TAIL_FILE" ]; then
		${RUN_AS_SPLUNK} tail -n 0 -F ${SPLUNK_HOME}/var/log/splunk/splunkd_stderr.log &
	else
		${RUN_AS_SPLUNK} tail -n 0 -F ${SPLUNK_TAIL_FILE} &
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
  * SPLUNK_GENERAL_TERMS - with the value '--accept-sgt-current-at-splunk-com', indicates acceptance of the latest Splunk General Terms: https://www.splunk.com/en_us/legal/splunk-general-terms.html (default: none)
  * SPLUNK_PASSWORD - password to log into this Splunk instance, you must include a password (default: none)
  * SPLUNK_STANDALONE_URL, SPLUNK_INDEXER_URL, ... - comma-separated list of resolvable aliases to properly bring-up a distributed environment.
                                                     This is optional for the UF, but necessary if you want to forward logs to another containerized Splunk instance
  * SPLUNK_BUILD_URL - URL to a Splunk Universal Forwarder build which will be installed (instead of the image's default build)
  * SPLUNK_DEPLOYMENT_SERVER - A network alias to Splunk deployment server
  * SPLUNK_ADD - '<monitor|add> <what_to_monitor|what_to_add>' - list of monitors separated by commas
  * SPLUNK_CMD - 'any splunk command' - execute any splunk commands separated by commas
  * SPLUNK_BEFORE_START_CMD - 'any splunk command to execute before Splunk starts' - execute any splunk commands separated by commas


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
