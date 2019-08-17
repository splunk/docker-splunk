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
apt-get update
apt-get install -y locales wget gnupg apt-utils
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
rm -f /usr/share/locale/locale.alias
ln -s /etc/locale.alias /usr/share/locale/locale.alias
locale-gen
localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
export LANG=en_US.utf8

# Set timezone to use UTC
ln -sf /usr/share/zoneinfo/UTC /etc/localtime
/usr/sbin/dpkg-reconfigure -f noninteractive tzdata

# Install additional dependencies
echo "deb http://ppa.launchpad.net/ansible/ansible/ubuntu xenial main" >> /etc/apt/sources.list
apt-key adv --keyserver https://keyserver.ubuntu.com --recv-keys 93C4A3FD7BB9C367
apt-get update

# put back tools for customer support
apt-cache show ansible
apt-get install -y --no-install-recommends ansible curl sudo libgssapi-krb5-2 busybox procps acl
apt-get install -y --no-install-recommends python-requests

cd /bin
ln -s busybox diff
ln -s busybox killall
ln -s busybox netstat
ln -s busybox nslookup
ln -s busybox ping
ln -s busybox ping6
ln -s busybox readline
ln -s busybox route
ln -s busybox syslogd
ln -s busybox tail
ln -s busybox traceroute
ln -s busybox vi
chmod u+s /bin/ping

apt-get clean autoclean
rm -rf /var/lib/apt/lists/*
