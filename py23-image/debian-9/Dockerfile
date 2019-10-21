ARG SPLUNK_PRODUCT=splunk
FROM ${SPLUNK_PRODUCT}-debian-9:latest
USER root

RUN apt-get update
RUN apt-get install -y gcc make \
    build-essential checkinstall libreadline-gplv2-dev libncursesw5-dev libssl-dev \
    libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev
# INFRA-15385: manual installation of python 3.7 as default distro version is 3.5
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
    && ln -s /usr/share/pyshared/lsb_release.py /usr/lib/python3.7/site-packages/lsb_release.py
#removing all intermediate dependencies. All the stuff below comes up to 200+MB
RUN apt-get remove --purge -y gcc make build-essential checkinstall libreadline-gplv2-dev libncursesw5-dev \
    libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev \
    && apt autoremove -y \
    && apt autoclean
RUN pip3 --no-cache-dir install ansible requests