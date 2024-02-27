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

localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
export LANG=en_US.utf8

yum -y update && yum -y install wget sudo epel-release
yum -y install busybox ansible python-requests python-jmespath

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

# Remove nproc limits
rm -rf /etc/security/limits.d/20-nproc.conf

# Clean
rm -rf /anaconda-post.log /var/log/anaconda/*

yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel xz-devel

PY_SHORT=${PYTHON_VERSION%.*}
wget -O /tmp/python.tgz https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz
#wget -O /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz.asc
#gpg --keyserver keys.openpgp.org --recv-keys $PYTHON_GPG_KEY_ID \
#    || gpg --keyserver pool.sks-keyservers.net --recv-keys $PYTHON_GPG_KEY_ID \
#    || gpg --keyserver pgp.mit.edu --recv-keys $PYTHON_GPG_KEY_ID \
#    || gpg --keyserver keyserver.pgp.com --recv-keys $PYTHON_GPG_KEY_ID
#gpg --verify /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc /tmp/python.tgz
#rm /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc
mkdir -p /tmp/pyinstall
tar -xzC /tmp/pyinstall/ --strip-components=1 -f /tmp/python.tgz
rm /tmp/python.tgz
cd /tmp/pyinstall
./configure --enable-optimizations --prefix=/usr --with-ensurepip=install
make altinstall
#make altinstall LDFLAGS="-Wl,--strip-all"
rm -rf /tmp/pyinstall
#ln -sf /usr/bin/python${PY_SHORT} /usr/bin/python
#ln -sf /usr/bin/pip${PY_SHORT} /usr/bin/pip
python --version

# Install splunk-ansible dependencies
cd /
#/usr/bin/python3.7 -m pip install --upgrade pip

#yum install -y python2
yum clean all
