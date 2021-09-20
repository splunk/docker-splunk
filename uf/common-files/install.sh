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

# map os arch to splunk arch labels
SPLUNK_ARCH=`arch`
if [[ $SPLUNK_ARCH = `s390x` ]]
then
  SPLUNK_ARCH="s390x"
elif [[ $SPLUNK_ARCH = `aarch64` ]]
then
  SPLUNK_ARCH="armv8"
else
  SPLUNK_ARCH="x86_64"
fi

# build the full splunk build url with proper arch
SPLUNK_BUILD_URL="${SPLUNK_BUILD_URL}${SPLUNK_ARCH}.tgz"

echo "Downloading Splunk and validating the checksum at: ${SPLUNK_BUILD_URL}"

wget -qO /tmp/`basename ${SPLUNK_BUILD_URL}` ${SPLUNK_BUILD_URL}
wget -qO /tmp/splunk.tgz.sha512 ${SPLUNK_BUILD_URL}.sha512
cd /tmp
echo "$(cat /tmp/splunk.tgz.sha512)" | sha512sum --check  --status
rm /tmp/splunk.tgz.sha512
tar -C /opt -zxf /tmp/`basename ${SPLUNK_BUILD_URL}`
mv ${SPLUNK_HOME}/etc ${SPLUNK_HOME}-etc
mkdir -p ${SPLUNK_HOME}/etc ${SPLUNK_HOME}/var
