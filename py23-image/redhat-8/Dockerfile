ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-redhat-8:latest
USER root

RUN microdnf -y --nodocs update \
    && microdnf -y --nodocs install python2-pip python2-devel \
    && pip2 --no-cache-dir install requests pyyaml jmespath \
    && ln -sf /usr/bin/python3.7 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip3 \
    && ln -sf /usr/bin/python3.7 /usr/bin/python \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip \
    && pip3 install --upgrade ansible==3.4.0 requests==2.25.1 pyyaml==5.4.1 jmespath==0.10.0
