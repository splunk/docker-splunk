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

FROM debian:stretch-slim
LABEL maintainer="support@splunk.com"

ARG SCLOUD_URL
ENV SCLOUD_URL=${SCLOUD_URL} \
    DEBIAN_FRONTEND=noninteractive \
    PYTHON_VERSION=3.7.10 \
    PYTHON_GPG_KEY_ID=0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D

COPY install.sh /install.sh
RUN /install.sh && rm -rf /install.sh
