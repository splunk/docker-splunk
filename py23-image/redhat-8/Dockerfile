ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-redhat-8:latest
USER root

RUN microdnf -y update \
    && microdnf -y install make gcc openssl-devel bzip2-devel libffi-devel
# INFRA-15385: manual installation of python 3.7 as default distro version is 3.6
RUN wget https://www.python.org/ftp/python/3.7.4/Python-3.7.4.tgz \
    && tar xzf Python-3.7.4.tgz \
    && cd Python-3.7.4 \
    && ./configure --enable-optimizations --prefix=/usr \
    && make install \
    && cd .. \
    && rm Python-3.7.4.tgz \
    && rm -r Python-3.7.4 \
    && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3.7 get-pip.py \
    && rm -f get-pip.py \
    #pip version is not automatically "fixed", unlike debian-based
    && ln -sf /usr/bin/pip2 /usr/bin/pip \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip3
#microdnf persists metadata which is a problem for removing packages. So have to clean first before removing. 
RUN microdnf clean all \
	&& microdnf remove -y gcc make openssl-devel bzip2-devel libffi-devel
RUN pip3 -q --no-cache-dir install requests ansible