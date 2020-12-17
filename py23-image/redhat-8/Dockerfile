ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-redhat-8:latest
USER root

RUN microdnf -y --nodocs update \
    && microdnf -y --nodocs install python2-pip python2-devel \
    && pip2 --no-cache-dir install requests ansible jmespath \
    && ln -sf /usr/bin/python3.7 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip3 \
    && ln -sf /usr/bin/python2 /usr/bin/python \
    && ln -sf /usr/bin/pip2 /usr/bin/pip
