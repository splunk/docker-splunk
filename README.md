# docker-splunk: Containerizing Splunk Enterprise

[![Build Status](https://circleci.com/gh/splunk/docker-splunk/tree/develop.svg?style=svg)](https://circleci.com/gh/splunk/docker-splunk/tree/develop)

Welcome to Splunk's official repository containing Dockerfiles for building Splunk Enterprise and Universal Forwarder deployments using containerization technology. This repository supports all Splunk roles and deployment topologies, and currently works on any Linux-based platform. 

The provisioning of these disjoint containers is handled by the [splunk-ansible](https://github.com/splunk/splunk-ansible) project. Please refer to [Ansible documentation](http://docs.ansible.com/) for more details about Ansible concepts and how it works. 

----

## Table of Contents

1. [Purpose](#purpose)
2. [Quickstart](#quickstart)
3. [Support](#support)
4. [Contributing](#contributing)
5. [License](#license)

----

## Purpose

##### What is Splunk Enterprise?
Splunk Enterprise is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results.

Please refer to [Splunk products](https://www.splunk.com/en_us/software.html) for more knowledge about the features and capabilities of Splunk, and how you can bring it into your organization.

##### What is docker-splunk?
This is the official source code repository for building Docker images of Splunk Enterprise and Splunk Universal Forwarder. By introducing containerization, we can marry the ideals of infrastructure-as-code and declarative directives to manage and run Splunk and its other product offerings.

This repository should be used by people interested in running Splunk in their container orchestration environments. With this Docker image, we support running a standalone development Splunk instance as easily as running a full-fledged distributed production cluster, all while maintaining the best practices and recommended standards of operating Splunk at scale.

## Quickstart
Use the following command to start a single standalone instance of Splunk Enterprise:
```
$ docker run -it -p 8000:8000 -e "SPLUNK_PASSWORD=<password>" -e "SPLUNK_START_ARGS=--accept-license" splunk/splunk:latest
```

Let's break down what this command does:
1. Starts a Docker container interactively using the `splunk/splunk:latest` image.
2. Expose a port mapping from the host's `8000` to the container's `8000`.
3. Specify a custom `SPLUNK_PASSWORD` - be sure to replace `<password>` with any string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile).
4. Accept the license agreement with `SPLUNK_START_ARGS=--accept-license`. This must be explicitly accepted on every `splunk/splunk` container, otherwise Splunk will not start.

After the container starts up successfully, you should be able to access SplunkWeb at http://localhost:8000 with `admin:<password>`.

For full usage instructions (including examples, advanced deployments, scenarios), please visit the [docker-splunk documentation](https://splunk.github.io/docker-splunk/) page.

## Support
When deploying this Docker image, please be mindful of the [supported architectures and platforms for containerized Splunk environments](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements#Containerized_computing_platforms). 

Additionally, please use the [GitHub issue tracker](https://github.com/splunk/docker-splunk/issues) to submit bugs or request features.

If you have questions or need support, you can:
* Post a question to [Splunk Answers](http://answers.splunk.com)
* Join the [#docker](https://splunk-usergroups.slack.com/messages/C1RH09ERM/) room in the [Splunk Slack channel](http://splunk-usergroups.slack.com)
* If you are a Splunk Enterprise customer with a valid support entitlement contract and have a Splunk-related question, you can also open a support case on the https://www.splunk.com/ support portal

## Contributing
We welcome feedback and contributions from the community! Please see our [contribution guidelines](docs/CONTRIBUTING.md) for more information on how to get involved. 

## License
Copyright 2018-2019 Splunk.

Distributed under the terms of our [license](docs/LICENSE.md), splunk-ansible is free and open source software.

## Authors
Splunk Inc. and the Splunk Community
