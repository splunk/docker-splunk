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

FROM centos:7

LABEL name="splunk" \
      maintainer="support@splunk.com" \
      vendor="splunk" \
      release="1" \
      summary="CentOS-7" \
      description="Splunk Enterprise is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results."

ARG BUSYBOX_URL

ENV BUSYBOX_URL=${BUSYBOX_URL} \
    PYTHON_VERSION=3.7.16 \
    PYTHON_GPG_KEY_ID=0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D

COPY install.sh /install.sh

RUN mkdir /licenses \
    && curl -o /licenses/apache-2.0.txt https://www.apache.org/licenses/LICENSE-2.0.txt \
    && /install.sh && rm -rf /install.sh

RUN curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output get-pip.py
RUN /usr/bin/python2 get-pip.py
RUN pip install "requests<2.29"
RUN pip install "requests_unixsocket<2.29"
RUN /usr/bin/python3.7 -m pip install "requests<2.29"
RUN /usr/bin/python3.7 -m pip install "requests_unixsocket<2.29"
