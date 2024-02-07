# Copyright 2018-2024 Splunk
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

ARG BASE_IMAGE=amazonlinux:2023
FROM ${BASE_IMAGE} as package

LABEL name="splunk" \
      maintainer="support@splunk.com" \
      vendor="splunk" \
      release="1" \
      summary="Amazon-Linux-2023" \
      description="Splunk Enterprise is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results."


COPY install.sh /install.sh

RUN mkdir /licenses \
    && curl -o /licenses/apache-2.0.txt https://www.apache.org/licenses/LICENSE-2.0.txt

RUN /install.sh && rm -rf /install.sh
