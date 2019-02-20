## Navigation

* [Preface](#preface)
* [System Requirements](#system-requirements)
* [Contact](#contact)
* [Support Violation](#support-violation)

----

## Preface
Splunk Enterprise contains many settings that allow customers to tailor their Splunk environment. However, because not all settings apply to all customers, Splunk will only support the most common subset of all configurations. Throughout this document, the term "supported" means you can contact Splunk Support for assistance with issues.

----

## System Requirements
At the current time, the Splunk Docker image officially supports running only on the following platforms:
1. Linux-based operating system (Debian, CentOS, etc.)
2. Chipset: 
    * `splunk/splunk` image supports x86-64 chipsets
    * `splunk/universalforwarder` image supports both x86-64 and x390x chipsets
3. Kernel version > 4.0
4. Docker engine
    * Docker Enterprise Engine 17.06.2 or later
    * Docker Community Engine 17.06.2 or later
5. `overlay2` Docker daemon storage driver
6. [Splunk hardware and capacity recommendations](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements)

For more details, please see the official [supported architectures and platforms for containerized Splunk environments](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements#Containerized_computing_platforms). 

----

## Contact
Splunk Enterprise Support offers assistance for all supported installations. Please contact them according to the instructions [here](https://www.splunk.com/en_us/support-and-services.html).

If you have additional questions or need more support, you can:
* Post a question to [Splunk Answers](http://answers.splunk.com)
* Join the [#docker](https://splunk-usergroups.slack.com/messages/C1RH09ERM/) room in the [Splunk Slack channel](http://splunk-usergroups.slack.com)
* If you are a Splunk Enterprise customer with a valid support entitlement contract and have a Splunk-related question, you can also open a support case on the https://www.splunk.com/ support portal

----

## Support Violation
In the following conditions, Splunk Support reserves the right to deem your installation unsupported and not provide assistance when issues arise: 
* You do not have an active support contract
* You are running Splunk Enterprise/Splunk Universal Forwarder in a container on a platform not officially supported by Splunk
* You are using features not officially supported by Splunk

In the event you fall into an unsupported state, you may find support on Splunk Answers, or through the open source communities found in this [docker-splunk](https://github.com/splunk/docker-splunk) GitHub project or the related [splunk-ansible](https://www.github.com/splunk/splunk-ansible) GitHub project.
