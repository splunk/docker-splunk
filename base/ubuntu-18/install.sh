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

# Generate UTF-8 char map and locale
apt-get update -y
apt-get install -y --no-install-recommends locales wget gnupg tzdata
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
rm -f /usr/share/locale/locale.alias
ln -s /etc/locale.alias /usr/share/locale/locale.alias
locale-gen
localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
export LANG=en_US.utf8

# Set timezone to use UTC
ln -sf /usr/share/zoneinfo/UTC /etc/localtime
/usr/sbin/dpkg-reconfigure -f noninteractive tzdata

# Install utility packages
apt-get install -y --no-install-recommends curl sudo libgssapi-krb5-2 busybox procps acl gcc make build-essential \
                                           libffi-dev libssl-dev libbz2-dev python3-apt python3-distutils \
                                           xz-utils ca-certificates zlib1g-dev python3.7 p11-kit liblz4-dev

# Install Python and necessary packages
wget -O get-pip.py https://bootstrap.pypa.io/get-pip.py
/usr/bin/python3.7 get-pip.py
ln -sf /usr/bin/python3.7 /usr/bin/python
ln -sf /usr/bin/pip3.7 /usr/bin/pip

# Install splunk-ansible dependencies
cd /
pip -q --no-cache-dir install six wheel requests cryptography==3.3.2 ansible==3.4.0 urllib3==1.26.5 jmespath --upgrade

# Remove tests packaged in python libs
find /usr/lib/ -depth \( -type f -a -name '*.pyc' -o -name '*.pyo' -o -name '*.a' \) -exec rm -rf '{}' \;
find /usr/lib/ -depth \( -type f -a -name 'wininst-*.exe' \) -exec rm -rf '{}' \;
ldconfig
apt-get remove -y --allow-remove-essential gcc libffi-dev libssl-dev make build-essential libbz2-dev xz-utils zlib1g-dev
apt-get autoremove -y --allow-remove-essential

# Install scloud
wget -O /usr/bin/scloud.tar.gz ${SCLOUD_URL}
tar -xf /usr/bin/scloud.tar.gz -C /usr/bin/
rm /usr/bin/scloud.tar.gz

# Enable busybox symlinks
cd /bin
BBOX_LINKS=( clear find diff hostname killall netstat nslookup ping ping6 readline route syslogd tail traceroute vi )
for item in "${BBOX_LINKS[@]}"
do
  ln -s busybox $item || true
done
chmod u+s /bin/ping

# Clean
apt clean autoclean
rm -rf /var/lib/apt/lists/*
