SHELL := /bin/bash
IMAGE_VERSION ?= "latest"
DOCKER_BUILD_FLAGS =
TEST_IMAGE_NAME = "spldocker"
SPLUNK_ANSIBLE_REPO ?= https://github.com/splunk/splunk-ansible.git
SPLUNK_ANSIBLE_BRANCH ?= develop
SPLUNK_COMPOSE ?= cluster_absolute_unit.yaml
# Set Splunk version/build parameters here to define downstream URLs and file names
SPLUNK_PRODUCT := splunk
SPLUNK_VERSION := 7.2.3
SPLUNK_BUILD := 06d57c595b80
ifeq ($(shell arch), s390x)
	SPLUNK_ARCH = s390x
else
	SPLUNK_ARCH = x86_64
endif

# Linux Splunk arguments
SPLUNK_LINUX_FILENAME ?= splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz
SPLUNK_LINUX_BUILD_URL ?= https://download.splunk.com/products/${SPLUNK_PRODUCT}/releases/${SPLUNK_VERSION}/linux/${SPLUNK_LINUX_FILENAME}
UF_LINUX_FILENAME ?= splunkforwarder-${SPLUNK_VERSION}-${SPLUNK_BUILD}-Linux-${SPLUNK_ARCH}.tgz
UF_LINUX_BUILD_URL ?= https://download.splunk.com/products/universalforwarder/releases/${SPLUNK_VERSION}/linux/${UF_LINUX_FILENAME}
# Windows Splunk arguments
SPLUNK_WIN_FILENAME ?= splunk-${SPLUNK_VERSION}-${SPLUNK_BUILD}-x64-release.msi
SPLUNK_WIN_BUILD_URL ?= https://download.splunk.com/products/${SPLUNK_PRODUCT}/releases/${SPLUNK_VERSION}/windows/${SPLUNK_WIN_FILENAME}
UF_WIN_FILENAME ?= splunkforwarder-${SPLUNK_VERSION}-${SPLUNK_BUILD}-x64-release.msi
UF_WIN_BUILD_URL ?= https://download.splunk.com/products/universalforwarder/releases/${SPLUNK_VERSION}/windows/${UF_WIN_FILENAME}

.PHONY: tests interactive_tutorials

all: splunk uf

ansible:
	if [ -d "splunk-ansible" ]; then \
		echo "Ansible directory exists - skipping clone"; \
	else \
		git clone ${SPLUNK_ANSIBLE_REPO} --branch ${SPLUNK_ANSIBLE_BRANCH}; \
	fi

##### Base images #####
base: base-debian-9 base-centos-7 base-windows-2016

base-debian-9:
	docker build ${DOCKER_BUILD_FLAGS} -t base-debian-9:${IMAGE_VERSION} ./base/debian-9

base-centos-7:
	docker build ${DOCKER_BUILD_FLAGS} -t base-centos-7:${IMAGE_VERSION} ./base/centos-7

base-windows-2016:
	docker build ${DOCKER_BUILD_FLAGS} -t base-windows-2016:${IMAGE_VERSION} ./base/windows-2016

##### Splunk images #####
splunk: ansible splunk-debian-9 splunk-centos-7

splunk-debian-9: base-debian-9 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/debian-9/Dockerfile \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--build-arg SPLUNK_FILENAME=${SPLUNK_LINUX_FILENAME} \
		-t splunk-debian-9:${IMAGE_VERSION} .

splunk-centos-7: base-centos-7 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/centos-7/Dockerfile \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--build-arg SPLUNK_FILENAME=${SPLUNK_LINUX_FILENAME} \
		-t splunk-centos-7:${IMAGE_VERSION} .

splunk-windows-2016: base-windows-2016 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/windows-2016/Dockerfile \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_WIN_BUILD_URL} \
		--build-arg SPLUNK_FILENAME=${SPLUNK_WIN_FILENAME} \
		-t splunk-windows-2016:${IMAGE_VERSION} .

##### UF images #####
uf: ansible uf-debian-9 uf-centos-7

uf-debian-9: base-debian-9 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/debian-9/Dockerfile \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		--build-arg SPLUNK_FILENAME=${UF_LINUX_FILENAME} \
		-t splunkforwarder-debian-9:${IMAGE_VERSION} .

uf-centos-7: base-centos-7 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/centos-7/Dockerfile \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		--build-arg SPLUNK_FILENAME=${UF_LINUX_FILENAME} \
		-t splunkforwarder-centos-7:${IMAGE_VERSION} .

uf-windows-2016: base-windows-2016 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/windows-2016/Dockerfile \
		--build-arg SPLUNK_BUILD_URL=${UF_WIN_BUILD_URL} \
		--build-arg SPLUNK_FILENAME=${UF_WIN_FILENAME} \
		-t splunkforwarder-windows-2016:${IMAGE_VERSION} .

##### Tests #####
sample-compose-up: sample-compose-down
	docker-compose -f test_scenarios/${SPLUNK_COMPOSE} up -d

sample-compose-down:
	docker-compose -f test_scenarios/${SPLUNK_COMPOSE} down --volumes --remove-orphans || true

test: clean ansible test_helper test_collection_cleanup

test_helper:
	@echo 'Starting container to run tests...'
	docker run -d --rm --name=${TEST_IMAGE_NAME} --net=host -v /var/run/docker.sock:/var/run/docker.sock -v $(shell pwd):$(shell pwd) --entrypoint /bin/sh python:2.7.15-alpine3.7 -c 'tail -f /dev/null'

	@echo 'Install test requirements'
	docker exec -i ${TEST_IMAGE_NAME} /bin/sh -c "pip install -r $(shell pwd)/tests/requirements.txt --upgrade"

	@echo 'Running the super awesome tests'
	docker exec -i ${TEST_IMAGE_NAME} /bin/sh -c "cd $(shell pwd); pytest -sv tests/ --junitxml testresults.xml"

test_collection_cleanup:
	docker cp ${TEST_IMAGE_NAME}:$(shell pwd)/testresults.xml testresults.xml || echo "no testresults.xml"

clean:
	rm -rf testresults.xml
	docker rm -f ${TEST_IMAGE_NAME} || true
	docker system prune -f --volumes
