#!/bin/bash
# Copyright 2018 Splunk
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

localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
export LANG=en_US.utf8

yum -y update && yum -y install wget sudo epel-release
yum -y install busybox ansible python-requests python-jmespath

# Install scloud
wget -P /usr/bin/ https://github.com/splunk/splunk-cloud-sdk-go/releases/download/v1.6.0/scloud_v3.0.0_linux_amd64.tar.gz
tar -xf /usr/bin/scloud_v3.0.0_linux_amd64.tar.gz -C /usr/bin/
rm /usr/bin/scloud_v3.0.0_linux_amd64.tar.gz

cd /bin
ln -s busybox killall
ln -s busybox netstat
ln -s busybox nslookup
ln -s busybox readline
ln -s busybox route
ln -s busybox syslogd
ln -s busybox traceroute
chmod u+s /bin/ping
groupadd sudo

echo "
## Allows people in group sudo to run all commands
%sudo  ALL=(ALL)       ALL" >> /etc/sudoers

# Clean
yum clean all
rm -rf /install.sh /anaconda-post.log /var/log/anaconda/*
