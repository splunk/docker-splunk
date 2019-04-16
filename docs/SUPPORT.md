## Navigation

* [Preface](#preface)
* [System Requirements](#system-requirements)
* [Contact](#contact)
* [Support Violation](#support-violation)

## Preface
Splunk Enterprise contains many settings that allow customers to tailor their Splunk environment. However, because not all settings apply to all customers, Splunk will only support the most common subset of all configurations. Throughout this document, the term "supported" means you can contact Splunk Support for assistance with issues.

## System Requirements
At the current time, this image only supports the Docker runtime engine and requires the following system prerequisites:
1. Linux-based operating system (Debian, CentOS, etc.)
2. Chipset: 
    * `splunk/splunk` image supports x86-64 chipsets
    * `splunk/universalforwarder` image supports both x86-64 and s390x chipsets
3. Kernel version > 4.0
4. Docker engine
    * Docker Enterprise Engine 17.06.2 or later
    * Docker Community Engine 17.06.2 or later
5. `overlay2` Docker daemon storage driver
    * Create a file /etc/docker/daemon.json on Linux systems, or C:\ProgramData\docker\config\daemon.json on Windows systems. Add {"storage-driver": "overlay2"} to the daemon.json. If you already have an existing json, please only add "storage-driver": "overlay2" as a key, value pair.

For more details, please see the official [supported architectures and platforms for containerized Splunk environments](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements#Containerized_computing_platforms) as well as [hardware and capacity recommendations](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements). 

If you intend for this containerized Splunk Enterprise deployment to be supported in your Enterprise Support Agreement, you must verify you meet all of the above "supported" requirements. Failure to do so will render your deployment in an "unsupported" state. 

## Contact
Splunk Support only provides support for the single instance Splunk Validated Architectures (S-Type), Universal Forwarders and Heavy Forwarders. For all other configurations, please contact Splunk Professional Services. Please contact them according to the instructions [here](https://www.splunk.com/en_us/support-and-services.html).

If you have additional questions or need more support, you can:
* Post a question to [Splunk Answers](http://answers.splunk.com)
* Join the [#docker](https://splunk-usergroups.slack.com/messages/C1RH09ERM/) room in the [Splunk Slack channel](http://splunk-usergroups.slack.com)
* If you are a Splunk Enterprise customer with a valid support entitlement contract and have a Splunk-related question, you can also open a support case on the https://www.splunk.com/ support portal

## Support Violation
In the following conditions, Splunk Support reserves the right to deem your installation unsupported and not provide assistance when issues arise: 
* You do not have an active support contract
* You are running Splunk Enterprise/Splunk Universal Forwarder in a container on a platform not officially supported by Splunk
* You are using features not officially supported by Splunk

In the event you fall into an unsupported state, you may find support on Splunk Answers, or through the open source communities found in this [docker-splunk](https://github.com/splunk/docker-splunk) GitHub project or the related [splunk-ansible](https://www.github.com/splunk/splunk-ansible) GitHub project.
