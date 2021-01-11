ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-debian-10:latest
USER root

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends libpython-dev ansible python-pip python-requests python-jmespath python-yaml \
    && ln -sf /usr/bin/python3.7 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip3 \
    && ln -sf /usr/bin/python3.7 /usr/bin/python \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip
