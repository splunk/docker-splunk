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

yum -y install glibc-locale-source glibc-langpack-en

localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
export LANG=en_US.utf8

yum -y update && yum -y install wget sudo epel-release make
yum -y install ansible python3-requests python3-jmespath

# Install busybox
wget -O /bin/busybox https://busybox.net/downloads/binaries/1.28.1-defconfig-multiarch/busybox-`arch`
chmod +x /bin/busybox

# Install scloud
wget -O /usr/bin/scloud.tar.gz ${SCLOUD_URL}
tar -xf /usr/bin/scloud.tar.gz -C /usr/bin/
rm /usr/bin/scloud.tar.gz

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

# symlink for python3
ln -s /bin/python3 /bin/python

# Clean
yum clean all
rm -rf /anaconda-post.log /var/log/anaconda/*
