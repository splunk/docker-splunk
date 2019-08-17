ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-redhat-8:latest
USER root

RUN microdnf -y --nodocs install python3
RUN alternatives --set python /usr/bin/python2
RUN pip3 -q --no-cache-dir install requests ansible