ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-redhat-8:latest
USER root

RUN microdnf -y --nodocs update \
    && microdnf -y --nodocs install python2 \
    && pip2 install --upgrade pip \
    && pip2 --no-cache-dir install requests pyyaml jmespath \
    && ln -sf /usr/bin/python3.13 /usr/bin/python \
    && ln -sf /usr/bin/pip3.13 /usr/bin/pip \
    && pip install --upgrade requests pyyaml jmespath
