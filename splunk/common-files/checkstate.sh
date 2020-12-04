#!/bin/bash

# Copyright 2018 Splunk

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

#NOTE: This script is no longer the prefered way of validation of container health
#And remains as it is referenced by splunk-operator until the dependency can be removed

#This script is used to retrieve and report the state of the container
#Although not actively in the container, it can be used to check the health
#of the splunk instance
#NOTE: If you plan on running the splunk container while keeping Splunk
# inactive for long periods of time, this script may give misleading
# health results

if [[ "" == "$NO_HEALTHCHECK" ]]; then
	goss -g /etc/goss.yml v
	exit $?
else
	#If NO_HEALTHCHECK is defined, ignore the healthcheck
	exit 0
fi
