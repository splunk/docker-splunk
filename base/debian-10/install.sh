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
apt update
apt install -y locales wget gnupg
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
apt update

# put back tools for customer support
apt-get install -y --no-install-recommends curl sudo libgssapi-krb5-2 busybox procps acl gcc libpython-dev libffi-dev libssl-dev
apt-get install -y --no-install-recommends python-pip python-setuptools python-requests python-yaml
pip --no-cache-dir install ansible
apt-get remove -y gcc libffi-dev libssl-dev libpython-dev
apt-get autoremove -y

cd /bin
ln -s busybox killall
ln -s busybox netstat
ln -s busybox nslookup
ln -s busybox ping
ln -s busybox ping6
ln -s busybox readline
ln -s busybox route
ln -s busybox syslogd
ln -s busybox traceroute
ln -s busybox vi
chmod u+s /bin/ping

apt clean autoclean
rm -rf /var/lib/apt/lists/*
