ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-centos-7:latest
USER root

RUN yum -y update
RUN yum -y install python36 python36-requests
RUN python3 -m ensurepip