#!/bin/bash

# Copyright 2023 Splunk

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
#

# This script is used to retrieve and report the state of the container
# Although not actively in the container, it can be used to check the health
# of the splunk instance
# NOTE: If you plan on running the splunk container while keeping Splunk
# inactive for long periods of time, this script may give misleading
# health results

# It is possible to disable the healthcheck utlizing one of the following methods:
# Set the NO_HEALTHCHECK variable
# Create the file "/tmp/healthcheck-disabled"

if [[ "" == "$NO_HEALTHCHECK" ]] && [[ ! -f /tmp/healthcheck-disabled ]]; then
	
	if [[ "false" == "$SPLUNKD_SSL_ENABLE" || "false" == "$(/opt/splunk/bin/splunk btool server list | grep enableSplunkdSSL | cut -d\  -f 3)" ]]; then
      SCHEME="http"
	else
      SCHEME="https"
    fi

	state="$(< $CONTAINER_ARTIFACT_DIR/splunk-container.state)"

	case "$state" in
	running|started)
	    curl --max-time 30 --fail --insecure $SCHEME://localhost:8089/
	    exit $?
	;;
	*)
	    exit 1
	esac
else
	exit 0
fi
