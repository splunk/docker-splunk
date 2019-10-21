ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-debian-10:latest
USER root

RUN apt-get update
RUN apt-get install -y --no-install-recommends python3 python3-pip python3-setuptools python3-requests python3-yaml
RUN pip3 --no-cache-dir install ansible