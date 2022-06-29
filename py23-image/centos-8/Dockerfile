ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-centos-8:latest
USER root

RUN yum -y update
RUN yum -y install gcc openssl-devel bzip2-devel libffi-devel python3-pip python2 python2-pip

# manual installation of python 3.7 as default distro version is 3.6
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
    # pip version is not automatically "fixed", unlike debian-based
    && ln -sf /usr/bin/pip2 /usr/bin/pip \
    && ln -sf /usr/bin/pip3.7 /usr/bin/pip3
    # add python alias
    # && ln -s /bin/python3 /bin/python

RUN yum remove -y --setopt=tsflags=noscripts gcc openssl-devel bzip2-devel libffi-devel \
    && yum autoremove -y \
    && yum clean all
RUN pip3 --no-cache-dir install ansible==3.4.0 requests==2.25.1 pyyaml==5.4.1 jmespath==0.10.0 \
    && pip --no-cache-dir install requests==2.25.1 pyyaml==5.4.1 jmespath==0.10.0
