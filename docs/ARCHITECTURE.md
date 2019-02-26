## Navigation

* [Architecture](#architecture)
    * [Base image](#base-image)
    * [Splunk Enterprise image](#splunk-enterprise-image)
    * [Universal Forwarder image](#universal-forwarder-image)
    * [Dynamic inventory](#dynamic-inventory)
* [Building Images](#building-images)

----

## Architecture

##### Base Image  

```
$ make base-debian-9
```

The directory `base/debian-9` contains a Dockerfile to create a base image on top
of which all the other images are built. In order to minimize image size and provide
a stable foundation for other images to build on, we elected to use `debian:stretch-slim` for our base image. `debian:stretch-slim` gives us the latest version of the Linux
Debian operating system in a tiny 55 megabytes. In the future, we plan to add
support for additional operating systems.

##### Splunk Enterprise Image  

```
$ make splunk-debian-9
```

The directory `splunk/debian-9` contains a Dockerfile that extends the base image
by installing Splunk and adding tools for provisioning. It extends `base-debian-9`
by installing the application and preparing the environment for provisioning.
Advanced Splunk provisioning capabilities are provided through the utilization 
of an entrypoint script and playbooks published separately via the
[Splunk Ansible Repository](https://github.com/splunk/splunk-ansible).

##### Universal Forwarder Image  

```
$ make splunkforwarder-debian-9
```

This image is similar to the Splunk Enterprise Image, except the more light-weight
Splunk Universal Forwarder package is installed instead.

----

## Building Images

Note that you will need to install [Docker](https://docs.docker.com/install/). 

Run the following command to build all the images:

```
 $> make all 
```

For more fine-grained control of which images to build, please refer to the `Makefile`.
