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
apt-get install -y --no-install-recommends locales wget gnupg apt-utils
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
apt-get install -y --no-install-recommends curl sudo libgssapi-krb5-2 busybox procps acl gcc make \
                                           libffi-dev libssl-dev make build-essential libbz2-dev \
                                           wget xz-utils ca-certificates zlib1g-dev liblz4-dev

# Install Python and necessary packages
PY_SHORT=${PYTHON_VERSION%.*}
wget -O /tmp/python.tgz https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz
wget -O /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz.asc
apt-get install dirmngr -y
gpg --keyserver keys.openpgp.org --recv-keys $PYTHON_GPG_KEY_ID \
    || gpg --keyserver pool.sks-keyservers.net --recv-keys $PYTHON_GPG_KEY_ID \
    || gpg --keyserver pgp.mit.edu --recv-keys $PYTHON_GPG_KEY_ID \
    || gpg --keyserver keyserver.pgp.com --recv-keys $PYTHON_GPG_KEY_ID
gpg --verify /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc /tmp/python.tgz
rm /tmp/Python-gpg-sig-${PYTHON_VERSION}.tgz.asc
mkdir -p /tmp/pyinstall
tar -xzC /tmp/pyinstall/ --strip-components=1 -f /tmp/python.tgz
rm /tmp/python.tgz
cd /tmp/pyinstall
./configure --enable-optimizations --prefix=/usr --with-ensurepip=install
make altinstall LDFLAGS="-Wl,--strip-all"
rm -rf /tmp/pyinstall
ln -sf /usr/bin/python${PY_SHORT} /usr/bin/python
ln -sf /usr/bin/pip${PY_SHORT} /usr/bin/pip
# For ansible apt module
cd /tmp
apt-get download python3-apt=1.4.3
dpkg -x python3-apt_1.4.3_amd64.deb python3-apt
rm python3-apt_1.4.3_amd64.deb
cp -r /tmp/python3-apt/usr/lib/python3/dist-packages/* /usr/lib/python${PY_SHORT}/site-packages/
cd /usr/lib/python${PY_SHORT}/site-packages/
cp apt_pkg.cpython-35m-x86_64-linux-gnu.so apt_pkg.so
cp apt_inst.cpython-35m-x86_64-linux-gnu.so apt_inst.so
rm -rf /tmp/python3-apt
# Install splunk-ansible dependencies
cd /
pip -q --no-cache-dir install six wheel requests cryptography==3.3.2 ansible==3.4.0 urllib3==1.26.5 jmespath --upgrade
# Remove tests packaged in python libs
find /usr/lib/ -depth \( -type d -a -not -wholename '*/ansible/plugins/test' -a \( -name test -o -name tests -o -name idle_test \) \) -exec rm -rf '{}' \;
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
