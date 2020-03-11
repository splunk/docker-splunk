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

ARG SPLUNK_BASE_IMAGE=splunk-debian-9

FROM ${SPLUNK_BASE_IMAGE}:latest

# Grab args from Makefile
ARG SPARK_VERSION=2.3.3
ARG HADOOP_VERSION=2.7
ARG JDK_VERSION="8u242"
ARG JDK_BUILD="b08"
ARG SPARK_URL=https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz
ARG JDK_URL=https://github.com/AdoptOpenJDK/openjdk8-binaries/releases/download/jdk${JDK_VERSION}-${JDK_BUILD}/OpenJDK8U-jre_x64_linux_hotspot_${JDK_VERSION}${JDK_BUILD}.tar.gz

USER root

# setup environment variables
ENV JAVA_HOME=/opt/jdk \
    SPARK_HOME=/opt/spark \
    SPARK_MASTER_PORT=7777 \
    SPARK_MASTER_WEBUI_PORT=8009 \
    SPARK_WORKER_WEBUI_PORT=7000 \
    ANSIBLE_USER=ansible

# download and install Spark
RUN wget -O /tmp/spark.tgz ${SPARK_URL} \
    && tar -C /tmp -zxvf /tmp/spark.tgz \
    && mkdir -p ${SPARK_HOME} ${SPARK_HOME}/eventlog \
    && mv /tmp/spark-*/* ${SPARK_HOME} \
    && chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPARK_HOME}

# download and install JDK (JRE)
RUN wget -O /tmp/jdk.tgz ${JDK_URL} \
    && tar -C /tmp -zxvf /tmp/jdk.tgz \
    && mkdir -p ${JAVA_HOME} \
    && mv /tmp/jdk*-jre/* ${JAVA_HOME} \
    && chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${JAVA_HOME}

# add entrypoint and update permissions
COPY spark/setenv.sh /opt/spark/setenv.sh
RUN chmod a+x /opt/spark/setenv.sh \
    && chmod -R a+r /opt/spark

USER ${ANSIBLE_USER}
VOLUME [ "/opt/spark" ]