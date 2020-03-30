## Navigation

* [Preface](#preface)
* [System requirements](#system-requirements)
* [Contact](#contact)
* [Support violation](#support-violation)

## Preface
Splunk Enterprise contains many settings that allow customers to tailor their Splunk environment. However, because not all settings apply to all customers, Splunk will only support the most common subset of all configurations. Throughout this document, the term "supported" means you can contact Splunk Support for assistance with issues.

## System requirements
In order to run this Docker image, you need the following prerequisites and dependencies installed on each node you plan on deploying the container:
* Linux-based operating system, such as Debian, CentOS, and so on.
* Chipset:
    * `splunk/splunk` image supports x86-64 chipsets
    * `splunk/universalforwarder` image supports both x86-64 and s390x chipsets

For more details, see the official [supported architectures and platforms for containerized Splunk software environments](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements#Containerized_computing_platforms) as well as [hardware and capacity recommendations](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements). Basic instructions to [deploy and run Splunk Enterprise inside containers](https://docs.splunk.com/Documentation/Splunk/latest/Installation/DeployandrunSplunkEnterpriseinsideDockercontainers) are also available.

If you intend for this containerized Splunk Enterprise deployment to be supported in your Enterprise Support Agreement, you must verify you meet all of the above supported requirements. Failure to do so will render your deployment in an unsupported state. See [Support Violation](#support-violation) below.

## Contact
Splunk Support only provides support for the single instance Splunk Validated Architectures (S-Type), Universal Forwarders and Heavy Forwarders. For all other configurations, [contact Splunk Professional Services](https://www.splunk.com/en_us/support-and-services.html).

For additional support, you can:
* Post a question to [Splunk Answers](http://answers.splunk.com).
* [Join us on Slack](https://docs.splunk.com/Documentation/Community/1.0/community/Chat#Join_us_on_Slack) and post in the [#docker](https://splunk-usergroups.slack.com/messages/C1RH09ERM/) channel.

If you are a Splunk Enterprise customer with a valid support entitlement contract and have a Splunk-related question, you can
* Open a support case on the <https://www.splunk.com/> support portal.

## Support violation
In the following conditions, Splunk Support reserves the right to deem your installation unsupported and not provide assistance when issues arise:
* You do not have an active support contract.
* You are running Splunk Enterprise and/or Splunk Universal Forwarder in a container on a platform not officially supported by Splunk.
* You are using features not officially supported by Splunk.

In the event you fall into an unsupported state, you may find support on [Splunk Answers](http://answers.splunk.com) or through the open-source communities found on GitHub for this [docker-splunk](https://github.com/splunk/docker-splunk) project or the related [splunk-ansible](https://www.github.com/splunk/splunk-ansible) project.
