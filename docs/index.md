# Welcome to the docker-splunk documentation!

Welcome to Splunk's official documentation on containerizing Splunk Enterprise and Splunk Universal Forwarder deployments with Docker.

#### What is Splunk Enterprise?
[Splunk Enterprise](https://www.splunk.com/en_us/software/splunk-enterprise.html) is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results.

Learn more about the features and capabilities of [Splunk Products](https://www.splunk.com/en_us/software.html) and how you can [bring them into your organization](https://www.splunk.com/en_us/enterprise-data-platform.html).

#### What is docker-splunk?
This is the official source code repository for building Docker images of Splunk Enterprise and Splunk Universal Forwarder. By introducing containerization, we can marry the ideals of infrastructure-as-code and declarative directives to manage and run Splunk and its other product offerings.

This repository should be used by people interested in running Splunk in their container orchestration environments. With this Docker image, we support running a standalone development Splunk instance as easily as running a full-fledged distributed production cluster, all while maintaining the best practices and recommended standards of operating Splunk at scale.

The provisioning of these disjoint containers is handled by the [splunk-ansible](https://github.com/splunk/splunk-ansible) project. See the [Ansible documentation](http://docs.ansible.com/) for more details about Ansible concepts and how it works.

---

#### Table of Contents

* [Introduction](INTRODUCTION.md)
* [Getting Started](SETUP.md)
    * [Requirements](SETUP.md#requirements)
    * [Installation](SETUP.md#installation)
    * [Run](SETUP.md#run)
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
* [License](LICENSE.md)
