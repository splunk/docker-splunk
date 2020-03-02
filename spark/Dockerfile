# Copyright 2020 Splunk
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

ARG SPLUNK_BASE_IMAGE=base-debian-10

# Download and unpack Splunk Enterprise
FROM ${SPLUNK_BASE_IMAGE}:latest as package
ARG SPLUNK_BUILD_URL
COPY splunk/common-files/make-minimal-exclude.py /tmp
RUN python /tmp/make-minimal-exclude.py ${SPLUNK_BUILD_URL} > /tmp/splunk-minimal-exclude.list \
    && wget -qO /tmp/splunk.tgz ${SPLUNK_BUILD_URL} \
    && wget -qO /tmp/splunk.tgz.md5 ${SPLUNK_BUILD_URL}.md5 \
    && test $(md5sum /tmp/splunk.tgz | sed 's,\([a-z0-9]*\).*,\1,') = $(cat /tmp/splunk.tgz.md5 | sed 's,MD5.*=.\([a-z0-9]*\).*,\1,') \
    && mkdir -p /minimal/splunk/var /extras/splunk/var \
    && tar -C /minimal/splunk --strip 1 --exclude-from=/tmp/splunk-minimal-exclude.list -zxf /tmp/splunk.tgz \
    && tar -C /extras/splunk --strip 1 --wildcards --files-from=/tmp/splunk-minimal-exclude.list -zxf /tmp/splunk.tgz \
    && mv /minimal/splunk/etc /minimal/splunk-etc \
    && mv /extras/splunk/etc /extras/splunk-etc \
    && mkdir -p /minimal/splunk/etc /minimal/splunk/share/splunk/search_mrsparkle/modules.new
COPY splunk/common-files/apps /extras/splunk-etc/apps/

# Grab args from Makefile
ARG SPARK_VERSION=2.3.3
ARG HADOOP_VERSION=2.7
ARG JDK_VERSION="8u212"
ARG JDK_BUILD="b03"
ARG SPARK_URL=https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz
ARG JDK_URL=https://github.com/AdoptOpenJDK/openjdk8-binaries/releases/download/jdk${JDK_VERSION}-${JDK_BUILD}/OpenJDK8U-jre_x64_linux_hotspot_${JDK_VERSION}${JDK_BUILD}.tar.gz

# download and install Spark
RUN wget -O /tmp/spark.tgz $SPARK_URL \
    && tar -C /tmp -zxvf /tmp/spark.tgz \
    && mkdir -p /minimal/spark /minimal/spark/eventlog \
    && mv /tmp/spark-*/* /minimal/spark

# download and install JDK (JRE)
RUN wget -O /tmp/jdk.tgz $JDK_URL \
    && tar -C /tmp -zxvf /tmp/jdk.tgz \
    && mkdir -p /minimal/jdk \
    && mv /tmp/jdk*-jre/* /minimal/jdk

# add entrypoint and update permissions
COPY [ "splunk/common-files/entrypoint.sh", "splunk/common-files/checkstate.sh", "splunk/common-files/createdefaults.py", "/sbin/" ]
COPY spark/setenv.sh /minimal/spark/setenv.sh
RUN chmod a+x /sbin/entrypoint.sh /minimal/spark/setenv.sh \
    && chmod -R a+r /minimal/spark

# Create final image
FROM ${SPLUNK_BASE_IMAGE}:latest
LABEL maintainer="support@splunk.com"

# setup environment variables
ENV JAVA_HOME=/opt/jdk \
    SPARK_HOME=/opt/spark \
    SPARK_MASTER_PORT=7777 \
    SPARK_MASTER_WEBUI_PORT=8009 \
    SPARK_WORKER_WEBUI_PORT=7000 \
    PATH=$PATH:/opt/jdk/bin:/opt/spark/bin \
    DEBIAN_FRONTEND=noninteractive \
    SPLUNK_HOME=/opt/splunk \
    SPLUNK_GROUP=splunk \
    SPLUNK_USER=splunk \
    SPLUNK_ANSIBLE_HOME=/opt/ansible \
    CONTAINER_ARTIFACT_DIR=/opt/container_artifact

# prevent adding /opt/splunk/bin/python to python path
ENV HOME=${SPLUNK_ANSIBLE_HOME}

# Currently kubernetes only accepts UID and not USER field to
# start a container as a particular user. So we create Splunk
# user with pre-determined UID.
ARG UID=41812
ARG GID=41812

# Simple script used to populate/upgrade splunk/etc directory
COPY [ "splunk/common-files/updateetc.sh", "/sbin/" ]

# add splunk user and group
RUN groupadd -r -g ${GID} ${SPLUNK_GROUP} \
    && useradd -r -m -u ${UID} -g ${GID} -s /sbin/nologin -d ${SPLUNK_HOME} ${SPLUNK_USER} \
    && mkdir -p /mnt/jdk /mnt/spark \
    && chown -R splunk.splunk ${SPLUNK_HOME} /mnt/jdk /mnt/spark \
    && chmod 755 /sbin/updateetc.sh

# copy package files
COPY --from=package --chown=splunk:splunk /minimal /opt
COPY --from=package [ "/sbin/entrypoint.sh", "/sbin/checkstate.sh", "/sbin/createdefaults.py", "/sbin/" ]
COPY --chown=${SPLUNK_USER}:${SPLUNK_GROUP} splunk-ansible ${SPLUNK_ANSIBLE_HOME}

RUN sed -i -e 's/%sudo\s\+ALL=(ALL\(:ALL\)\?)\s\+ALL/%sudo ALL=NOPASSWD:ALL/g' /etc/sudoers \
    && sudo echo -e '\splunk ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers \
    && usermod -aG sudo ${SPLUNK_USER} \
    && usermod -aG ${SPLUNK_GROUP} ${SPLUNK_USER} \
    && mkdir ${CONTAINER_ARTIFACT_DIR} \
    && chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} /opt \
    && chmod -R 775 ${CONTAINER_ARTIFACT_DIR} \
    && chmod -R 555 ${SPLUNK_ANSIBLE_HOME} \
    && chmod 775 ${SPLUNK_ANSIBLE_HOME} \
    && chmod 755 /sbin/entrypoint.sh /sbin/createdefaults.py /sbin/checkstate.sh

USER ${SPLUNK_USER}
HEALTHCHECK --interval=30s --timeout=30s --start-period=3m --retries=5 CMD /sbin/checkstate.sh || exit 1
WORKDIR ${SPLUNK_ANSIBLE_HOME}
ENTRYPOINT [ "/sbin/entrypoint.sh" ]
CMD "start-service"

EXPOSE 8000/tcp 8089/tcp
EXPOSE 8000 8065 8088 8089 8191 9887 9997
VOLUME [ "/opt/spark", "/opt/splunk/etc", "/opt/splunk/var" ]
