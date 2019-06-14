# Copyright 2019 Splunk
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

#
# Prepare new files in a temporary base image
#
FROM ${SPLUNK_BASE_IMAGE}:latest as package

ARG SPARK_URL=https://archive.apache.org/dist/spark/spark-2.3.0/spark-2.3.0-bin-hadoop2.7.tgz
ARG JDK_URL=https://github.com/AdoptOpenJDK/openjdk8-binaries/releases/download/jdk8u212-b04/OpenJDK8U-jre_x64_linux_hotspot_8u212b04.tar.gz

# download and install Spark
RUN wget -O /tmp/spark.tgz $SPARK_URL
RUN tar -C /tmp -zxvf /tmp/spark.tgz
RUN mkdir -p /opt/spark /opt/spark/eventlog
RUN mv /tmp/spark-*/* /opt/spark

# download and install JDK (JRE)
RUN wget -O /tmp/jdk.tgz $JDK_URL
RUN tar -C /tmp -zxvf /tmp/jdk.tgz
RUN mkdir -p /opt/jdk
RUN mv /tmp/jdk*-jre/* /opt/jdk

# add entrypoint and update permissions
ADD spark/entrypoint.sh /opt/spark/entrypoint.sh
ADD spark/setenv.sh /opt/spark/setenv.sh
RUN chmod a+x /opt/spark/entrypoint.sh /opt/spark/setenv.sh
RUN chmod -R a+r /opt/spark


#
# Create final image
#
FROM ${SPLUNK_BASE_IMAGE}:latest
LABEL maintainer="support@splunk.com"

# setup environment variables
ENV JAVA_HOME=/opt/jdk
ENV SPARK_HOME=/opt/spark
ENV SPARK_MASTER_HOSTNAME=127.0.0.1
ENV SPARK_MASTER_PORT=7777
ENV SPARK_MASTER_WEBUI_PORT=8009
ENV SPARK_WORKER_WEBUI_PORT=7000
ENV PATH=$PATH:/opt/jdk/bin:/opt/spark/bin
ENV DEBIAN_FRONTEND=noninteractive
ENV SPLUNK_HOME=/opt/splunk \
    SPLUNK_GROUP=splunk \
    SPLUNK_USER=splunk

# Currently kubernetes only accepts UID and not USER field to
# start a container as a particular user. So we create Splunk
# user with pre-determined UID.
ARG UID=41812
ARG GID=41812

# add splunk user and group
RUN groupadd -r -g ${GID} ${SPLUNK_GROUP} \
    && useradd -r -m -u ${UID} -g ${GID} -s /sbin/nologin -d ${SPLUNK_HOME} ${SPLUNK_USER} \
    && mkdir -p /mnt/jdk /mnt/spark \
    && chown -R splunk.splunk ${SPLUNK_HOME} /mnt/jdk /mnt/spark

# copy package files
COPY --from=package --chown=splunk:splunk /opt /opt

# run as user splunk
USER ${SPLUNK_USER}
WORKDIR ${SPLUNK_HOME}

ENTRYPOINT /opt/spark/entrypoint.sh
