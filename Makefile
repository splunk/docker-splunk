SHELL := /bin/bash
IMAGE_VERSION ?= "latest"
NONQUOTE_IMAGE_VERSION := $(patsubst "%",%,$(IMAGE_VERSION))
DOCKER_BUILD_FLAGS ?=
SPLUNK_ANSIBLE_REPO ?= https://github.com/splunk/splunk-ansible.git
SPLUNK_ANSIBLE_BRANCH ?= develop
SPLUNK_COMPOSE ?= cluster_absolute_unit.yaml
# Set Splunk version/build parameters here to define downstream URLs and file names
SPLUNK_PRODUCT := splunk
SPLUNK_VERSION := 8.0.4
SPLUNK_BUILD := 767223ac207f
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

# Security Scanner Variables
SCANNER_DATE := `date +%Y-%m-%d`
SCANNER_DATE_YEST := `TZ=GMT+24 +%Y:%m:%d`
SCANNER_VERSION := v8
SCANNER_LOCALIP := $(shell ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | awk '{print $1}' | head -n 1)
SCANNER_IMAGES_TO_SCAN := splunk-debian-9 splunk-debian-10 splunk-centos-7 splunk-redhat-8 uf-debian-9 uf-debian-10 uf-centos-7 uf-redhat-8 splunk-py23-debian-9 splunk-py23-debian-10 splunk-py23-centos-7 splunk-py23-redhat-8 uf-py23-debian-9 uf-py23-debian-10 uf-py23-centos-7 uf-py23-redhat-8
CONTAINERS_TO_SAVE := splunk-debian-9 splunk-debian-10 splunk-centos-7 splunk-redhat-8 uf-debian-9 uf-debian-10 uf-centos-7 uf-redhat-8 splunk-py23-debian-9 splunk-py23-debian-10 splunk-py23-centos-7 splunk-py23-redhat-8 uf-py23-debian-9 uf-py23-debian-10 uf-py23-centos-7 uf-py23-redhat-8
ifeq ($(shell uname), Linux)
	SCANNER_FILE = clair-scanner_linux_amd64
else ifeq ($(shell uname), Darwin)
	SCANNER_FILE = clair-scanner_darwin_amd64
else
	SCANNER_FILE = clair-scanner_windows_amd64.exe
endif


.PHONY: tests interactive_tutorials

all: splunk uf splunk-py23 uf-py23

ansible:
	@if [ -d "splunk-ansible" ]; then \
		echo "Ansible directory exists - skipping clone"; \
	else \
		git clone ${SPLUNK_ANSIBLE_REPO} --branch ${SPLUNK_ANSIBLE_BRANCH}; \
	fi
	@cd splunk-ansible && git rev-parse HEAD > version.txt
	@cat splunk-ansible/version.txt

##### Base images #####
base: base-debian-9 base-debian-10 base-centos-7 base-redhat-8 base-windows-2016

base-debian-10:
	docker build ${DOCKER_BUILD_FLAGS} -t base-debian-10:${IMAGE_VERSION} ./base/debian-10

base-debian-9:
	docker build ${DOCKER_BUILD_FLAGS} -t base-debian-9:${IMAGE_VERSION} ./base/debian-9

base-centos-7:
	docker build ${DOCKER_BUILD_FLAGS} -t base-centos-7:${IMAGE_VERSION} ./base/centos-7

base-redhat-8:
	docker build ${DOCKER_BUILD_FLAGS} --label version=${SPLUNK_VERSION} -t base-redhat-8:${IMAGE_VERSION} ./base/redhat-8

base-windows-2016:
	docker build ${DOCKER_BUILD_FLAGS} -t base-windows-2016:${IMAGE_VERSION} ./base/windows-2016

##### Minimal images #####
minimal: minimal-debian-9 minimal-debian-10 minimal-centos-7 minimal-redhat-8

minimal-debian-9: base-debian-9
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-9 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target minimal -t minimal-debian-9:${IMAGE_VERSION} .	

minimal-debian-10: base-debian-10
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-10 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target minimal -t minimal-debian-10:${IMAGE_VERSION} .	

minimal-centos-7: base-centos-7
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-centos-7 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target minimal -t minimal-centos-7:${IMAGE_VERSION} .	

minimal-redhat-8: base-redhat-8
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-redhat-8 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target minimal -t minimal-redhat-8:${IMAGE_VERSION} .

##### Bare images #####
bare: bare-debian-9 bare-debian-10 bare-centos-7 bare-redhat-8

bare-debian-9: base-debian-9
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-9 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target bare -t bare-debian-9:${IMAGE_VERSION} .	

bare-debian-10: base-debian-10
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-10 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target bare -t bare-debian-10:${IMAGE_VERSION} .	

bare-centos-7: base-centos-7
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-centos-7 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target bare -t bare-centos-7:${IMAGE_VERSION} .	

bare-redhat-8: base-redhat-8
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-redhat-8 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		--target bare -t bare-redhat-8:${IMAGE_VERSION} .

##### Splunk images #####
splunk: ansible splunk-debian-9 splunk-debian-10 splunk-centos-7 splunk-redhat-8

splunk-debian-9: base-debian-9 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-9 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		-t splunk-debian-9:${IMAGE_VERSION} .

splunk-debian-10: base-debian-10 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-10 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		-t splunk-debian-10:${IMAGE_VERSION} .

splunk-centos-7: base-centos-7 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-centos-7 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		-t splunk-centos-7:${IMAGE_VERSION} .

splunk-redhat-8: base-redhat-8 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-redhat-8 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_LINUX_BUILD_URL} \
		-t splunk-redhat-8:${IMAGE_VERSION} .

splunk-windows-2016: base-windows-2016 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f splunk/windows-2016/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-windows-2016 \
		--build-arg SPLUNK_BUILD_URL=${SPLUNK_WIN_BUILD_URL} \
		-t splunk-windows-2016:${IMAGE_VERSION} .

##### UF images #####
uf: ansible uf-debian-9 uf-debian-10 uf-centos-7 uf-redhat-8

ufbare-debian-9: base-debian-9 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-9 \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		--target bare -t ufbare-debian-9:${IMAGE_VERSION} .

ufbare-debian-10: base-debian-10 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-10 \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		--target bare -t ufbare-debian-10:${IMAGE_VERSION} .

uf-debian-9: base-debian-9 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-9 \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		-t uf-debian-9:${IMAGE_VERSION} .

uf-debian-10: base-debian-10 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-debian-10 \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		-t uf-debian-10:${IMAGE_VERSION} .

uf-centos-7: base-centos-7 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-centos-7 \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		-t uf-centos-7:${IMAGE_VERSION} .

uf-redhat-8: base-redhat-8 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/common-files/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-redhat-8 \
		--build-arg SPLUNK_BUILD_URL=${UF_LINUX_BUILD_URL} \
		-t uf-redhat-8:${IMAGE_VERSION} .

uf-windows-2016: base-windows-2016 ansible
	docker build ${DOCKER_BUILD_FLAGS} \
		-f uf/windows-2016/Dockerfile \
		--build-arg SPLUNK_BASE_IMAGE=base-windows-2016 \
		--build-arg SPLUNK_BUILD_URL=${UF_WIN_BUILD_URL} \
		-t uf-windows-2016:${IMAGE_VERSION} .


##### Python 3 support #####
splunk-py23: splunk-py23-debian-9 splunk-py23-debian-10 splunk-py23-centos-7 splunk-py23-redhat-8

splunk-py23-debian-9: splunk-debian-9
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/debian-9/Dockerfile \
		--build-arg SPLUNK_PRODUCT=splunk \
		-t splunk-py23-debian-9:${IMAGE_VERSION} .

splunk-py23-debian-10: splunk-debian-10
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/debian-10/Dockerfile \
		--build-arg SPLUNK_PRODUCT=splunk \
		-t splunk-py23-debian-10:${IMAGE_VERSION} .

splunk-py23-centos-7: splunk-centos-7
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/centos-7/Dockerfile \
		--build-arg SPLUNK_PRODUCT=splunk \
		-t splunk-py23-centos-7:${IMAGE_VERSION} .

splunk-py23-redhat-8: splunk-redhat-8
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/redhat-8/Dockerfile \
		--build-arg SPLUNK_PRODUCT=splunk \
		-t splunk-py23-redhat-8:${IMAGE_VERSION} .

uf-py23: uf-py23-debian-9 uf-py23-debian-10 uf-py23-centos-7 uf-py23-redhat-8

uf-py23-debian-9: uf-debian-9
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/debian-9/Dockerfile \
		--build-arg SPLUNK_PRODUCT=uf \
		-t uf-py23-debian-9:${IMAGE_VERSION} .

uf-py23-debian-10: uf-debian-10
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/debian-10/Dockerfile \
		--build-arg SPLUNK_PRODUCT=uf \
		-t uf-py23-debian-10:${IMAGE_VERSION} .

uf-py23-centos-7: uf-centos-7
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/centos-7/Dockerfile \
		--build-arg SPLUNK_PRODUCT=uf \
		-t uf-py23-centos-7:${IMAGE_VERSION} .

uf-py23-redhat-8: uf-redhat-8
	docker build ${DOCKER_BUILD_FLAGS} \
		-f py23-image/redhat-8/Dockerfile \
		--build-arg SPLUNK_PRODUCT=uf \
		-t uf-py23-redhat-8:${IMAGE_VERSION} .


##### Tests #####
sample-compose-up: sample-compose-down
	docker-compose -f test_scenarios/${SPLUNK_COMPOSE} up -d 

sample-compose-down:
	docker-compose -f test_scenarios/${SPLUNK_COMPOSE} down --volumes --remove-orphans || true

test: clean ansible test_setup all run_tests_centos7 run_tests_redhat8 run_tests_debian9

test_centos7: clean ansible splunk-centos-7 uf-centos-7 test_setup run_tests_centos7

test_redhat8: clean ansible splunk-redhat-8 uf-redhat-8 test_setup run_tests_redhat8

test_debian9: clean ansible splunk-debian-9 uf-debian-9 test_setup run_tests_debian9

test_debian10: clean ansible splunk-debian-10 uf-debian-10 test_setup run_tests_debian10

run_tests_centos7:
	@echo 'Running the super awesome tests; CentOS 7'
	pytest -sv tests/test_docker_splunk.py --platform centos-7 --junitxml test-results/centos7-result/testresults_centos7.xml

run_tests_redhat8:
	@echo 'Running the super awesome tests; RedHat 8'
	pytest -sv tests/test_docker_splunk.py --platform redhat-8 --junitxml test-results/redhat8-result/testresults_redhat8.xml

test_setup:
	@echo 'Install test requirements'
	pip install --upgrade pip
	pip install -r $(shell pwd)/tests/requirements.txt --upgrade
	mkdir test-results/centos7-result || true
	mkdir test-results/debian9-result || true
	mkdir test-results/debian10-result || true
	mkdir test-results/redhat8-result || true

run_tests_debian9:
	@echo 'Running the super awesome tests; Debian 9'
	pytest -sv tests/test_docker_splunk.py --platform debian-9 --junitxml test-results/debian9-result/testresults_debian9.xml

run_tests_debian10:
	@echo 'Running the super awesome tests; Debian 10'
	pytest -sv tests/test_docker_splunk.py --platform debian-10 --junitxml test-results/debian10-result/testresults_debian10.xml

save_containers:
	@echo 'Saving the following containers:${CONTAINERS_TO_SAVE}'
	mkdir test-results/saved_images || true
	$(foreach image,${CONTAINERS_TO_SAVE}, echo "Currently saving: ${image}"; docker save ${image} --output test-results/saved_images/${image}.tar; echo "Compressing: ${image}.tar"; gzip test-results/saved_images/${image}.tar; )

test_python3_all: test_splunk_python3_all test_uf_python3_all

test_splunk_python3_all: test_splunk_centos7_python3 test_splunk_redhat8_python3 test_splunk_debian9_python3 test_splunk_debian10_python3

test_uf_python3_all: test_uf_centos7_python3 test_uf_redhat8_python3 test_uf_debian9_python3 test_uf_debian10_python3

test_splunk_centos7_python3:
	$(call test_python3_installation,splunk-py23-centos-7)

test_splunk_redhat8_python3:
	$(call test_python3_installation,splunk-py23-redhat-8)

test_splunk_debian9_python3:
	$(call test_python3_installation,splunk-py23-debian-9)

test_splunk_debian10_python3:
	$(call test_python3_installation,splunk-py23-debian-10)

test_uf_centos7_python3:
	$(call test_python3_installation,uf-py23-centos-7)

test_uf_redhat8_python3:
	$(call test_python3_installation,uf-py23-redhat-8)

test_uf_debian9_python3:
	$(call test_python3_installation,uf-py23-debian-9)

test_uf_debian10_python3:
	$(call test_python3_installation,uf-py23-debian-10)

define test_python3_installation
docker run -d --rm --name $1 -it $1 bash
docker exec -it $1 bash -c 'if [[ $$(python3 -V) =~ "Python 3" ]] ; then echo "$$(python3 -V) installed" ; else echo "No Python3 installation found" ; docker kill $1 ; exit 1 ; fi'
docker kill $1
endef

test_python2_all: test_splunk_python2_all test_uf_python2_all

test_splunk_python2_all: test_splunk_centos7_python2 test_splunk_redhat8_python2 test_splunk_debian9_python2 test_splunk_debian10_python2

test_uf_python2_all: test_uf_centos7_python2 test_uf_redhat8_python2 test_uf_debian9_python2 test_uf_debian10_python2

test_splunk_centos7_python2:
	$(call test_python2_installation,splunk-py23-centos-7)

test_splunk_redhat8_python2:
	$(call test_python2_installation,splunk-py23-redhat-8)

test_splunk_debian9_python2:
	$(call test_python2_installation,splunk-py23-debian-9)

test_splunk_debian10_python2:
	$(call test_python2_installation,splunk-py23-debian-10)

test_uf_centos7_python2:
	$(call test_python2_installation,uf-py23-centos-7)

test_uf_redhat8_python2:
	$(call test_python2_installation,uf-py23-redhat-8)

test_uf_debian9_python2:
	$(call test_python2_installation,uf-py23-debian-9)

test_uf_debian10_python2:
	$(call test_python2_installation,uf-py23-debian-10)

#python2 version print to stderr, hence the 2>&1
define test_python2_installation
docker run -d --rm --name $1 -it $1 bash
docker exec -it $1 bash -c 'if [[ $$(python -V 2>&1) =~ "Python 2" ]] ; then echo "$$(python -V 2>&1) is the default python" ; else echo "Python is not default to python2" ; docker kill $1 ; exit 1 ; fi'
docker kill $1
endef

test_debian10_image_size:
	$(call test_image_size,splunk-debian-10)

define test_image_size
docker pull splunk/splunk:edge
CUR_SIZE=$$(docker image inspect $1:latest --format='{{.Size}}') ; \
EDGE_SIZE=$$(docker image inspect splunk/splunk:edge --format='{{.Size}}') ; \
echo "current $1 image size = "$$CUR_SIZE ; \
echo "edge image size = "$$EDGE_SIZE ; \
if [[ $$CUR_SIZE -gt $$EDGE_SIZE*140/100 ]] ; then echo "current image size is 40% more than edge image" ; exit 1 ; fi
endef

setup_clair_scanner:
	mkdir clair-scanner-logs
	mkdir test-results/cucumber
	docker stop clair_db || true
	docker rm clair_db || true
	docker stop clair || true
	docker rm clair || true
	docker pull arminc/clair-db:${SCANNER_DATE} || docker pull arminc/clair-db:${SCANNER_DATE_YEST} || echo "WARNING: Failed to pull daily image, defaulting to latest" >> clair-scanner-logs/clair_setup_errors.log ; docker pull arminc/clair-db:latest
	docker run -d --name clair_db arminc/clair-db:${SCANNER_DATE} || docker run -d --name clair_db arminc/clair-db:${SCANNER_DATE_YEST} || docker run -d --name clair_db arminc/clair-db:latest
	docker run -p 6060:6060 --link clair_db:postgres -d --name clair --restart on-failure arminc/clair-local-scan:v2.0.6
	wget https://github.com/arminc/clair-scanner/releases/download/${SCANNER_VERSION}/${SCANNER_FILE}
	mv ${SCANNER_FILE} clair-scanner
	chmod +x clair-scanner
	echo "Waiting for clair daemon to start"
	retries=0 ; while( ! wget -T 10 -q -O /dev/null http://0.0.0.0:6060/v1/namespaces ) ; do sleep 1 ; echo -n "." ; if [ $$retries -eq 10 ] ; then echo " Timeout, aborting." ; exit 1 ; fi ; retries=$$(($$retries+1)) ; done
	echo "Daemon started."

run_clair_scan:
	$(foreach image,${SCANNER_IMAGES_TO_SCAN}, mkdir test-results/clair-scanner-${image}; ./clair-scanner -c http://0.0.0.0:6060 --ip ${SCANNER_LOCALIP} -r test-results/clair-scanner-${image}/results.json -l clair-scanner-logs/${image}.log -w clair-whitelist.yml ${image}:${NONQUOTE_IMAGE_VERSION} || true ; python clair_to_junit_parser.py test-results/clair-scanner-${image}/results.json --output test-results/clair-scanner-${image}/results.xml ; )

setup_and_run_clair: setup_clair_scanner run_clair_scan

clean:
	docker stop clair_db || true
	docker rm clair_db || true
	docker stop clair || true
	docker rm clair || true
	rm -rf .pytest_cache || true
	rm -rf clair-scanner || true
	rm -rf clair-scanner-logs || true
	rm -rf test-results/* || true
	docker rm -f ${TEST_IMAGE_NAME} || true
	docker system prune -f --volumes

clean_ansible:
	rm -rf splunk-ansible

dev_loop:
	SPLUNK_IMAGE="splunk-debian-10:latest" make sample-compose-down && sleep 15  &&  DOCKER_BUILD_FLAGS="--no-cache" make all && sleep 15 && SPLUNK_IMAGE="splunk-debian-10:latest" make sample-compose-up
