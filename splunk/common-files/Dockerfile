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

ARG SPLUNK_BASE_IMAGE=base-debian-10:latest

#
# Download and unpack Splunk Enterprise
#
FROM ${SPLUNK_BASE_IMAGE} as package
ARG SPLUNK_VERSION
ARG SPLUNK_BUILD
ARG SPLUNK_URL_BASE=https://d7wz6hmoaavd0.cloudfront.net/products
COPY splunk/common-files/make-minimal-exclude.py /tmp
RUN export SPLUNK_ARCH=$(if [ "$(arch)" = "s390x"  ]; then echo s390x; elif [ "$(arch)" = "aarch64"  ]; then echo armv8 ;else echo x86_64 ;fi) \
    && echo SPLUNK_VERSION=${SPLUNK_VERSION} SPLUNK_BUILD=${SPLUNK_BUILD} SPLUNK_ARCH=${SPLUNK_ARCH} CONTAINER_ARCH=$(arch) \
    && python /tmp/make-minimal-exclude.py ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz > /tmp/splunk-minimal-exclude.list \
    && echo "Downloading Splunk and validating the checksum at: ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz" \
    && wget -qO /tmp/`basename ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz` ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz \
    && wget -qO /tmp/splunk.tgz.sha512 ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz.sha512 \
    && cd /tmp ;ls -l;cat /tmp/splunk.tgz.sha512\
    && echo "$(cat /tmp/splunk.tgz.sha512)" | sha512sum --check  --status \
    && rm /tmp/splunk.tgz.sha512 \
    && mkdir -p /minimal/splunk/var /extras/splunk/var \
    && tar -C /minimal/splunk --strip 1 --exclude-from=/tmp/splunk-minimal-exclude.list -zxf /tmp/`basename ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz` \
    && tar -C /extras/splunk --strip 1 --wildcards --files-from=/tmp/splunk-minimal-exclude.list -zxf /tmp/`basename ${SPLUNK_URL_BASE}/splunk/releases/${SPLUNK_VERSION}/linux/splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz` \
    && mv /minimal/splunk/etc /minimal/splunk-etc \
    && mv /extras/splunk/etc /extras/splunk-etc \
    && mkdir -p /minimal/splunk/etc /minimal/splunk/share/splunk/search_mrsparkle/modules.new
COPY splunk/common-files/apps /extras/splunk-etc/apps/


#
# Minimal Splunk base image with many files excluded, intended for internal and experimental use
#
FROM ${SPLUNK_BASE_IMAGE} as minimal
LABEL maintainer="support@splunk.com"
ENV SPLUNK_HOME=/opt/splunk \
    SPLUNK_GROUP=splunk \
    SPLUNK_USER=splunk
ENV TMPSPLUNKDIR=${SPLUNK_HOME}/tmp
ENV TMPETCDIR=${TMPSPLUNKDIR}/etc

# Currently kubernetes only accepts UID and not USER field to
# start a container as a particular user. So we create Splunk
# user with pre-determined UID.
ARG UID=41812
ARG GID=41812

# Simple script used to populate/upgrade splunk/etc directory
COPY [ "splunk/common-files/updateetc.sh", "/sbin/" ]

# Setup users and groups
RUN groupadd -r -g ${GID} ${SPLUNK_GROUP} \
    && useradd -r -m -u ${UID} -g ${GID} -s /bin/bash ${SPLUNK_USER} \
    && chmod 755 /sbin/updateetc.sh

COPY --from=package --chown=splunk:splunk /minimal /opt

USER ${SPLUNK_USER}
WORKDIR ${SPLUNK_HOME}
EXPOSE 8000/tcp 8089/tcp


#
# Bare Splunk Enterprise Image without Ansible (BYO entrypoint)
#
FROM minimal as bare
COPY --from=package --chown=splunk:splunk /extras /opt
EXPOSE 8000 8065 8088 8089 8191 9887 9997
VOLUME [ "/opt/splunk/etc", "/opt/splunk/var" ]



#
# Full Splunk Enterprise Image with Ansible
#
FROM bare

ARG SPLUNK_VERSION
ARG SPLUNK_BUILD

ENV SPLUNK_ROLE=splunk_standalone \
    SPLUNK_DEFAULTS_URL=${SPLUNK_DEFAULTS_URL} \
    SPLUNK_ANSIBLE_HOME=/opt/ansible \
    ANSIBLE_USER=ansible \
    ANSIBLE_GROUP=ansible \
    CONTAINER_ARTIFACT_DIR=/opt/container_artifact

USER root

COPY [ "splunk/common-files/entrypoint.sh", "splunk/common-files/createdefaults.py", "splunk/common-files/checkstate.sh", "/sbin/" ]
COPY splunk-ansible ${SPLUNK_ANSIBLE_HOME}

# Set sudo rights
RUN sed -i -e 's/%sudo\s\+ALL=(ALL\(:ALL\)\?)\s\+ALL/%sudo ALL=NOPASSWD:ALL\nansible ALL=(splunk)NOPASSWD:ALL/g' /etc/sudoers \
    && echo 'Create the ansible user/group' \
    && groupadd -r ${ANSIBLE_GROUP} \
    && useradd -r -m -g ${ANSIBLE_GROUP} -s /bin/bash ${ANSIBLE_USER} \
    && usermod -aG sudo ${ANSIBLE_USER} \
    && usermod -aG ${ANSIBLE_GROUP} ${SPLUNK_USER} \
    && echo 'Container Artifact Directory is a place for all artifacts and logs that are generated by the provisioning process. The directory is owned by the user "ansible".' \
    && mkdir ${CONTAINER_ARTIFACT_DIR} \
    && chown -R ${ANSIBLE_USER}:${ANSIBLE_GROUP} ${CONTAINER_ARTIFACT_DIR} \
    && chmod -R 775 ${CONTAINER_ARTIFACT_DIR} \
    && chmod -R 555 ${SPLUNK_ANSIBLE_HOME} \
    && chgrp ${ANSIBLE_GROUP} ${SPLUNK_ANSIBLE_HOME} ${SPLUNK_ANSIBLE_HOME}/ansible.cfg \
    && chmod 775 ${SPLUNK_ANSIBLE_HOME} \
    && chmod 664 ${SPLUNK_ANSIBLE_HOME}/ansible.cfg \
    && chmod 755 /sbin/entrypoint.sh /sbin/createdefaults.py /sbin/checkstate.sh

USER ${ANSIBLE_USER}
HEALTHCHECK --interval=30s --timeout=30s --start-period=3m --retries=5 CMD /sbin/checkstate.sh || exit 1
ENTRYPOINT [ "/sbin/entrypoint.sh" ]
CMD [ "start-service" ]
