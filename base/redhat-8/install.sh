#!/bin/bash
# Copyright 2018-2020 Splunk
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

# Per: https://github.com/rpm-software-management/microdnf/issues/50
mkdir -p /run/user/$UID
# reinstalling local en def for now, removed in minimal image https://bugzilla.redhat.com/show_bug.cgi?id=1665251
microdnf -y --nodocs install glibc-langpack-en

#Currently there is no access to the UTF-8 char map, the following command is commented out until
#the base container can generate the locale
#localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

#We get around the gen above by forcing the language install, and then point to it.
export LANG=en_US.utf8

rpm -e --nodeps tzdata
microdnf -y --nodocs install wget sudo shadow-utils procps tar tzdata
#install busybox direct from the multiarch since epel isn't availible yet for redhat8
wget -O /bin/busybox https://busybox.net/downloads/binaries/1.28.1-defconfig-multiarch/busybox-`arch`
chmod +x /bin/busybox
microdnf -y --nodocs update gnutls kernel-headers
microdnf -y --nodocs install python2-pip python2-devel redhat-rpm-config gcc libffi-devel openssl-devel
pip2 --no-cache-dir install requests ansible
microdnf -y remove gcc openssl-devel redhat-rpm-config python2-devel device-mapper-libs device-mapper trousers systemd systemd-pam \
                   dwz dbus dbus-common dbus-daemon dbus-tools dbus-libs go-srpm-macros iptables-libs annobin cryptsetup-libs \
                   ocaml-srpm-macros openblas-srpm-macros qt5-srpm-macros perl-srpm-macros rust-srpm-macros ghc-srpm-macros \
                   efi-srpm-macros python-srpm-macros python-rpm-macros python3-rpm-macros python2-rpm-macros python3-rpm-generators \
                   zip unzip xkeyboard-config file file-libs findutils diffutils kmod-libs util-linux libxkbcommon libffi-devel \
                   elfutils-libs elfutils-debuginfod-client elfutils-default-yama-scope pcre2-devel pcre2-utf16 pcre2-utf32 \
                   libfdisk libpcap libseccomp libselinux-devel libutempter binutils libxcrypt-devel cpp glibc-devel glibc-headers \
                   krb5-devel libkadm5 platform-python-pip

cd /bin
ln -s python2 python || true
ln -s busybox diff || true
ln -s busybox hostname || true
ln -s busybox killall || true
ln -s busybox netstat || true
ln -s busybox nslookup || true
ln -s busybox ping || true
ln -s busybox ping6 || true
ln -s busybox readline || true
ln -s busybox route || true
ln -s busybox syslogd || true
ln -s busybox traceroute || true
chmod u+s /bin/ping
groupadd sudo

echo "
## Allows people in group sudo to run all commands
%sudo  ALL=(ALL)       ALL" >> /etc/sudoers

# Clean
microdnf clean all
rm -rf /install.sh /anaconda-post.log /var/log/anaconda/*
