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

# NOTE that since OpenShift Container Platform 3.11
# the container catalog moved from registry.access.redhat.com to registry.redhat.io
# So at some point before they deprecate the old registry we have to make sure that
# we have access to the new registry and change where we pull the ubi image from.
FROM registry.access.redhat.com/ubi8/ubi-minimal:8.2-267
LABEL name="splunk" \
      maintainer="support@splunk.com" \
      vendor="splunk" \
      release="1" \
      summary="UBI 8 Docker image of Splunk Enterprise" \
      description="Splunk Enterprise is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results."

COPY install.sh /install.sh

RUN mkdir /licenses \
    && curl -o /licenses/apache-2.0.txt https://www.apache.org/licenses/LICENSE-2.0.txt \
    && curl -o /licenses/EULA_Red_Hat_Universal_Base_Image_English_20190422.pdf https://www.redhat.com/licenses/EULA_Red_Hat_Universal_Base_Image_English_20190422.pdf \
    && /install.sh && rm -rf /install.sh
