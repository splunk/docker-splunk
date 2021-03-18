# Welcome to the Docker-Splunk documentation!

Welcome to the official Splunk documentation on containerizing Splunk Enterprise and Splunk Universal Forwarder deployments with Docker.

### What is Splunk Enterprise?
[Splunk Enterprise](https://www.splunk.com/en_us/software/splunk-enterprise.html) is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results.

See [Splunk Products](https://www.splunk.com/en_us/software.html) for more information about the features and capabilities of Splunk products and how you can [bring them into your organization](https://www.splunk.com/en_us/enterprise-data-platform.html).

### What is Docker-Splunk?
The [Docker-Splunk project](https://github.com/splunk/docker-splunk) is the official source code repository for building Docker images of Splunk Enterprise and Splunk Universal Forwarder. By introducing containerization, we can marry the ideals of infrastructure-as-code and declarative directives to manage and run Splunk Enterprise.

This repository should be used by people interested in running Splunk in their container orchestration environments. With this Docker image, we support running a standalone development Splunk instance as easily as running a full-fledged distributed production cluster, all while maintaining the best practices and recommended standards of operating Splunk at scale.

The provisioning of these disjoint containers is handled by the [Splunk-Ansible](https://github.com/splunk/splunk-ansible) project. Refer to the [Splunk-Ansible documentation](https://splunk.github.io/splunk-ansible/) and the [Ansible User Guide](https://docs.ansible.com/ansible/latest/user_guide/index.html) for more details.

---

### Table of Contents

* [Introduction](INTRODUCTION.md)
* [Getting Started](SETUP.md)
    * [Requirements](SETUP.md#requirements)
    * [Install](SETUP.md#install)
    * [Deploy](SETUP.md#deploy)
* [Examples](EXAMPLES.md)
* [Advanced Usage](ADVANCED.md)
    * [Runtime configuration](ADVANCED.md#runtime-configuration)
    * [Install apps](ADVANCED.md#install-apps)
    * [Apply Splunk license](ADVANCED.md#apply-splunk-license)
    * [Create custom configs](ADVANCED.md#create-custom-configs)
    * [Enable SmartStore](ADVANCED.md#enable-smartstore)
    * [Use a deployment server](ADVANCED.md#use-a-deployment-server)
    * [Deploy distributed topology](ADVANCED.md#deploy-distributed-topology)
    * [Enable SSL communication](ADVANCED.md#enable-ssl-internal-communication)
    * [Build from source](ADVANCED.md#build-from-source)
* [Persistent Storage](STORAGE_OPTIONS.md)
* [Architecture](ARCHITECTURE.md)
* [Troubleshooting](TROUBLESHOOTING.md)
* [Contributing](CONTRIBUTING.md)
* [Support](SUPPORT.md)
* [Changelog](CHANGELOG.md)
* [License](LICENSE.md)
