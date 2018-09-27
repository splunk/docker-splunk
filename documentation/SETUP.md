## Splunk officially supported installation platforms

Splunk Enterprise contains many settings that allow customers to tailor their Splunk environment. Because not all settings apply to all customers, Splunk will only support the most common subset of all configurations. Below is a list of supported platforms and base operating systems. Please check back periodically as our support matrix will expand over time.
Throughout this document, the term "Supported" means you can contact Splunk Support for assistance with issues. 
In the following conditions, Splunk Support reserves the right to deem your installation in an unsupported state and not provide assistance when issues arise: 
* You do not have an active support contract
* You are running Splunk Enterprise / Splunk Universal Forwarder in a container on a platform not officially supported by Splunk
* You are using features not officially supported by Splunk

In the event you fall into an unsupported state, you may find support on Splunk Answers, or through the open source communities found on [GitHub for Splunk-Ansible](https://www.github.com/splunk/splunk-ansible) or [GitHub for Splunk-Docker](https://github.com/splunk/docker-splunk).

##### Supported Operating Systems:

Linux kernel versions above 4.x.

##### Supported Docker Engine Versions:

* Docker Enterprise Engine 17.06.2 or later
* Docker Community Engine 17.06.2 or later

** Note: ** Splunk Support does not provide assistance with the advanced usage of an operator such as the scale command. Splunk Support will only provide assistance with the functionality of running the container on the systems listed above, and cannot support setup and configuration of the a service level object to be used for docker-compose or kubectl. Please consult the Docker or Kubernetes documentation regarding best practices for building services. 

**Note:** Splunk Support only provides support for the single instance Splunk Validated Architectures (S-Type). For all other configurations, please contact Splunk Professional Services.

##### Required Hardware #####

All instances must be at or above the minimum server specifications found in the [Splunk installation manual](http://docs.splunk.com/Documentation/Splunk/7.0.0/Installation/SystemRequirements). 
Additionally, the Docker container at this time is also limited to the following base installation chipsets:
* x86-64
* s390x (Universal Forwarder only)

Volumes used for persistence of the Splunk Enterprise data inside the Docker container must be one of the supported filesystems listed in the [Splunk installation manual](http://docs.splunk.com/Documentation/Splunk/latest/Installation/SystemRequirements).

## Prerequisites ##
1. Install the appropriate [Docker Engine](https://docs.docker.com/engine/installation/#supported-platforms) for your operating system
2. If you intend for the containerized Splunk Enterprise deployment to be supported by your Enterprise Support Agreement, you must verify you meet all of the 
above "supported" requirements. Failure to do so will render your deployment in an "unsupported" state.

##### Install Splunk Enterprise Docker containers (Supported) 

Download the required image to your local Docker image library. 
```
$ docker pull splunk/splunk:latest
```

##### Install Splunk Univeral Forwarder Docker containers (Supported) #####

Download the required image to your local Docker image library. 
```
$ docker pull splunk/splunk-uf:latest
```

## Starting Splunk Enterprise ##

For a basic standalone Splunk environment, run the following command:
```
$ docker run -d -p 8000:8000 -e 'SPLUNK_START_ARGS=--accept-license' -e 'SPLUNK_PASSWORD=<password>' splunk/splunk:latest
```
**Note:** The password supplied must conform to the default [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/7.1.2/Security/Configurepasswordsinspecfile)* 

The output of Docker's run command will be a long hash of numbers and letters.  These numbers and letters are the container id for your
Splunk Enterprise deployment.  Use "docker ps" to get the status of the new deployment. For example: 
```
docker ps -a -f id=9d790051bff3d8eb88da2d27b515140ff45f8f77a4bd57d6e5655d87cf3272fb 
```
```
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS                            PORTS                                                                                     NAMES
9d790051bff3        splunk-debian-9     "/sbin/entrypoint.sh…"   4 seconds ago       Up 3 seconds (health: starting)   4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:8000->8000/tcp   zen_hawking
```
Once the container has reached a "healthy" status, you can log in.  The exposed port will be listed under the port section.

```
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS                   PORTS                                                                                     NAMES
9d790051bff3        splunk-debian-9     "/sbin/entrypoint.sh…"   4 minutes ago       Up 4 minutes (healthy)   4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:8000->8000/tcp   zen_hawking
```
Ports with an IP address are container ports that can be accessed from external. Follow this [link](https://answers.splunk.com/answers/58888/what-are-the-ports-that-i-need-to-open.html) for more information on Splunk Enterprise's default ports.
```
4001/tcp, 
8065/tcp, 
8088-8089/tcp, 
8191/tcp, 
9887/tcp, 
9997/tcp, 
0.0.0.0:8000->8000/tcp  <-------  This is an exposed port accessible from external
```
In the above example, the port that is exposed is on the same port number which running inside the container.  If port 8000 was occupied by another service on localhost, this port will instead be
exposed at a higher port number.  By opening an Internet browser and travelling to the exposed address, such as `localhost:8000`, you will be prompted with a login page.
Log in to your deployment with the Splunk credentials `admin` and use the password you set during installation, or input from the SplunkUI.

## Starting Splunk Universal Forwarder ##

The Splunk Universal Forwarder is started in a similar way to Splunk Enterprise
```
$ docker run -d  -p 9997:9997 -e 'SPLUNK_START_ARGS=--accept-license' -e 'SPLUNK_PASSWORD=<password>' splunk/splunk-uf:latest
```
The Splunk Universal Forwarder however does not have a GUI, so you will not be able to access it through a web interface.
Instead, you can access the container directly by using the `docker exec` command.  After the container is in a "healthy" state, run the following:
```
docker exec -it <container-id> /bin/bash
```
```
splunk@<container-id>:/$
```
You are now logged into the container as the splunk user. Please see the [Configure the Universal Forwarder](http://docs.splunk.com/Documentation/Forwarder/7.1.2/Forwarder/Configuretheuniversalforwarder) in the Splunk Forwarder Manual for more information on configuring the Splunk Universal Forwarder.


## Enterprise Applications (Splunk Enterprise Security and Splunk IT Service Intelligence) ##
* Installation of Splunk Enterprise Security (ES) and Splunk IT Service Intelligence (ITSI) are not supported in this version. 
Please contact Splunk Services for more information on using these applications with Splunk Enterprise in a container.


## Clusters and Other Advanced Deployments ##

For information about more advanced deployments including search head and indexer clusters, please see `documentation/ADVANCED.md`. 

## Help ##

The open-source community for this project, and for the Splunk-Ansible project, can be found on their respective github.com repositories.
Splunk Enterprise Support offers assistance with all supported installations. Please contact them according to the instructions [here](https://www.splunk.com/en_us/support-and-services.html).

