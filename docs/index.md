# Welcome to the docker-splunk documentation!

Welcome to Splunk's official documentation regarding Dockerfiles for building Splunk Enterprise and Universal Forwarder images using containerization technology. This repository supports all Splunk roles and deployment topologies, and currently works on any Linux-based platform. 

The provisioning of these disjoint containers is handled by the [splunk-ansible](https://github.com/splunk/splunk-ansible) project. Please refer to [Ansible documentation](http://docs.ansible.com/) for more details about Ansible concepts and how it works. 

#### What is Splunk Enterprise?
Splunk Enterprise is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results.

Please refer to [Splunk products](https://www.splunk.com/en_us/software.html) for more knowledge about the features and capabilities of Splunk, and how you can bring it into your organization.

#### What is docker-splunk?
This is the official source code repository for building Docker images of Splunk Enterprise and Splunk Universal Forwarder. By introducing containerization, we can marry the ideals of infrastructure-as-code and declarative directives to manage and run Splunk and its other product offerings.

This repository should be used by people interested in running Splunk in their container orchestration environments. With this Docker image, we support running a standalone development Splunk instance as easily as running a full-fledged distributed production cluster, all while maintaining the best practices and recommended standards of operating Splunk at scale.

---

#### Table of Contents

* [Introduction](INTRODUCTION.md)
* [Getting Started](SETUP.md)
    * [Install](SETUP.md#install)
    * [Configure](SETUP.md#configure)
    * [Run](SETUP.md#run)
* [Examples](EXAMPLES.md)
* [Advanced Usage](ADVANCED.md)
    * [Runtime configuration](ADVANCED.md#runtime-configuration)
    * [Entrypoint Functions](ADVANCED.md#entrypoint-functions)
    * [Install apps](ADVANCED.md#install-apps)
    * [Apply Splunk license](ADVANCED.md#apply-splunk-license)
    * [Enabling SmartStore](ADVANCED.md#enabling-smartstore)
    * [Deploy distributed topology](ADVANCED.md#deploy-distributed-topology)
    * [Build from source](ADVANCED.md#build-from-source)
* [Persistent Storage](STORAGE_OPTIONS.md)
* [Architecture](ARCHITECTURE.md)
* [Troubleshooting](TROUBLESHOOTING.md)
* [Contributing](CONTRIBUTING.md)
* [Support](SUPPORT.md)
* [License](LICENSE.md)
