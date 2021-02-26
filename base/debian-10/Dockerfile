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

FROM debian:buster-slim
LABEL maintainer="support@splunk.com"

ARG SCLOUD_URL
ENV SCLOUD_URL=${SCLOUD_URL} \
    DEBIAN_FRONTEND=noninteractive \
    PYTHON_VERSION=3.7.10 \
    PYTHON_MD5=0b19e34a6dabc4bf15fdcdf9e77e9856

COPY install.sh /install.sh
RUN /install.sh && rm -rf /install.sh
