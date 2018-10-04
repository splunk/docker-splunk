# Welcome to the Splunk Docker GitHub repository

This is the official source code repository for building Docker images of Splunk Enterprise
and the Splunk Universal Forwarder. 

## What is Splunk Enterprise?

Splunk Enterprise is the platform for operational intelligence. The software lets
you collect, analyze, and act upon the untapped value of big data that your technology
infrastructure, security systems, and business applications generate. It gives you
insights to drive operational performance and business results.

## The Splunk Base Image:   ```base-debian-9```

The directory `base/debian-9` contains a Dockerfile to create a base image on top
of which all the other images are built. In order to minimize image size and provide
a stable foundation for other images to build on, we elected to use `debian:stretch-slim` for our base image. `debian:stretch-slim` gives us the latest version of the Linux
Debian operating system in a tiny 55 megabytes. In the future, we plan to add
support for additional operating systems.

## The Splunk Enterprise Image:   ```splunk-debian-9```

The directory `splunk/debian-9` contains a Dockerfile that extends the base image
by installing Splunk and adding tools for provisioning. It extends `base-debian-9`
by installing the application and preparing the environment for provisioning.
Advanced Splunk provisioning capabilities are provided through the utilization 
of an entrypoint script and playbooks published separately via the
[Splunk Ansible Repository](https://github.com/splunk/splunk-ansible).

## The Splunk Universal Forwarder Image:   ```splunkforwarder-debian-9```

This image is similar to the Splunk Enterprise Image, except the more light-weight
Splunk Universal Forwarder package is installed instead.


# Building

Note that you will need to install [Docker](https://docs.docker.com/install/). 

Run the following command to build all the images:

```
 $> make all 
```

For more fine-grained control of which images to build, please refer to the `Makefile`.


# Getting started

Use the following command to start a single instance of Splunk Enterprise:
```
 $> docker run -it -p 8000:8000 -e 'SPLUNK_START_ARGS=--accept-license' -e 'SPLUNK_PASSWORD=<password>' splunk-debian-9:latest start
```
Replace "<password>" with the initial password that you wish to use for logging into the Splunk admin
user account. You can then access Splunk at http://localhost:8000 with those credentials.

*Please note, the password supplied must conform to the default
[Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile)*

Notice that the license agreement has to be explicitly accepted. Splunk will not start
unless you pass the argument `--accept-license` to every container.

Use `Ctrl+C` to stop the container.

For more detailed requirements, instructions and scenarios, please see [SETUP](documentation/SETUP.md)

For information about more advanced deployments including search head and indexer
clusters, please see [ADVANCED](documentation/ADVANCED.md) 


# Get help and support

If you have questions or need support, you can:

* Post a question to [Splunk Answers](http://answers.splunk.com)
* Join the [Splunk Slack channel](http://splunk-usergroups.slack.com)
* Visit the #splunk channel on [EFNet Internet Relay Chat](http://www.efnet.org)
* Send an email to [docker-maint@splunk.com](mailto:docker-maint@splunk.com)

Please also see [TROUBLESHOOTING](documentation/TROUBLESHOOTING.md)


# License

See [LICENSING](documentation/LICENSING.md)


# Contributing

See [CONTRIBUTING](documentation/CONTRIBUTING.md)


# History

See [CHANGELOG](documentation/CHANGELOG.md)


# Authors

Splunk Inc. and the Splunk Community
