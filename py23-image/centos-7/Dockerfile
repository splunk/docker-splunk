ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-centos-7:latest
USER root

RUN yum -y update
RUN yum -y install python36 python36-requests
RUN python3 -m ensurepip
# INFRA-15385: manual installation of python 3.7 as default distro version is 3.6
RUN wget https://www.python.org/ftp/python/3.7.4/Python-3.7.4.tgz \
    && tar xzf Python-3.7.4.tgz \
    && cd Python-3.7.4 \
    && ./configure --enable-optimizations --prefix=/usr \
    && make altinstall \
    && cd .. \
    && rm Python-3.7.4.tgz \
    && rm -r Python-3.7.4 \