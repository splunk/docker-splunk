ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-redhat-8:latest
USER root

RUN microdnf -y --nodocs update \
    && microdnf -y --nodocs install python2 \
    && pip2 install --upgrade pip \
    && pip2 --no-cache-dir install requests pyyaml jmespath \
    && ln -sf /usr/bin/python3.9 /usr/bin/python \
    && ln -sf /usr/bin/pip3.9 /usr/bin/pip \
    && pip3 install --upgrade requests==2.25.1 pyyaml==5.4.1 jmespath==0.10.0
