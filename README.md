# docker-splunk: Containerizing Splunk Enterprise

[![Build Status](https://circleci.com/gh/splunk/docker-splunk/tree/develop.svg?style=svg)](https://circleci.com/gh/splunk/docker-splunk/tree/develop)

Welcome to Splunk's official repository containing Dockerfiles for building Splunk Enterprise and Universal Forwarder images using containerization technology.

The provisioning of these disjoint containers is handled by the [splunk-ansible](https://github.com/splunk/splunk-ansible) project. Please refer to [Ansible documentation](http://docs.ansible.com/) for more details about Ansible concepts and how it works. 

----

## Table of Contents

1. [Purpose](#purpose)
2. [Quickstart](#quickstart)
3. [Documentation](#documentation)
4. [Support](#support)
5. [Contributing](#contributing)
6. [License](#license)

----

## Purpose

##### What is Splunk Enterprise?
Splunk Enterprise is a platform for operational intelligence. Our software lets you collect, analyze, and act upon the untapped value of big data that your technology infrastructure, security systems, and business applications generate. It gives you insights to drive operational performance and business results.

Please refer to [Splunk products](https://www.splunk.com/en_us/software.html) for more knowledge about the features and capabilities of Splunk, and how you can bring it into your organization.

##### What is docker-splunk?
This is the official source code repository for building Docker images of Splunk Enterprise and Splunk Universal Forwarder. By introducing containerization, we can marry the ideals of infrastructure-as-code and declarative directives to manage and run Splunk Enterprise.

---

## Quickstart
Use the following command to start a single standalone instance of Splunk Enterprise:
```bash
$ docker run -it --name so1 -p 8000:8000 -e "SPLUNK_PASSWORD=<password>" -e "SPLUNK_START_ARGS=--accept-license" splunk/splunk:latest
```

Let's break down what this command does:
1. Starts a Docker container interactively using the `splunk/splunk:latest` image.
2. Expose a port mapping from the host's `8000` to the container's `8000`.
3. Specify a custom `SPLUNK_PASSWORD` - be sure to replace `<password>` with any string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile).
4. Accept the license agreement with `SPLUNK_START_ARGS=--accept-license`. This must be explicitly accepted on every `splunk/splunk` container, otherwise Splunk will not start.

After the container starts up successfully, you should be able to access SplunkWeb at http://localhost:8000 with `admin:<password>`.

To view the logs from the container created above, run:
```bash
$ docker logs -f so1
```

To enter the container and run some Splunk CLI commands:
```bash
# Defaults to "ansible" user
docker exec -it so1 /bin/bash
# Run shell as "splunk" user
docker exec -u splunk -it so1 bash
```

For an example of how to enable TCP 10514 for listening:
```bash
docker exec -u splunk so1 /opt/splunk/bin/splunk add tcp 10514 \
    -sourcetype syslog -resolvehost true \
    -auth "admin:${SPLUNK_PASSWORD}"
```

To install an app:
```bash
# Alternatively, apps can be installed at Docker run-time, ex:
# docker run -e SPLUNK_APPS_URL=http://web/app.tgz ...
docker exec -u splunk so1 /opt/splunk/bin/splunk install \
	/path/to/app.tar -auth "admin:${SPLUNK_PASSWORD}"
```

Additional information on Docker support for Splunk Enterprise can be found [here](https://docs.splunk.com/Documentation/Splunk/latest/Installation/DeployandrunSplunkEnterpriseinsideDockercontainers).

---

## Documentation
For full usage instructions (including examples, advanced deployments, scenarios), please visit the [docker-splunk documentation](https://splunk.github.io/docker-splunk/) page.

---

## Support
Please use the [GitHub issue tracker](https://github.com/splunk/docker-splunk/issues) to submit bugs or request features.

If you have additional questions or need more support, you can:
* Post a question to [Splunk Answers](http://answers.splunk.com)
* Join the [#docker](https://splunk-usergroups.slack.com/messages/C1RH09ERM/) room in the [Splunk Slack channel](http://splunk-usergroups.slack.com)
* If you are a Splunk Enterprise customer with a valid support entitlement contract and have a Splunk-related question, you can also open a support case on the https://www.splunk.com/ support portal

For more detailed informations on support, please see the official [support guidelines](docs/SUPPORT.md).

---

## Contributing
We welcome feedback and contributions from the community! Please see our [contribution guidelines](docs/CONTRIBUTING.md) for more information on how to get involved. 

--- 

## License
Copyright 2018-2020 Splunk.

Distributed under the terms of our [license](docs/LICENSE.md), splunk-ansible is free and open source software.

## Authors
Splunk Inc. and the Splunk Community
