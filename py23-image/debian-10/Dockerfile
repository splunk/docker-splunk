ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-debian-10:latest
USER root

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends libpython-dev python-pip python-requests python-jmespath python-yaml \
    && ln -sf /usr/bin/python3.7 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip3 \
    && ln -sf /usr/bin/python3.7 /usr/bin/python \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip \
    && pip3 install --upgrade ansible==3.4.0 requests==2.25.1 pyyaml==5.4.1 jmespath==0.10.0
