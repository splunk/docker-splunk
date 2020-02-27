# Splunk Enterprise Docker Container

**Use the Docker containers for Splunk Enterprise and the Splunk Universal Forwarder to quickly deploy Splunk software, with the ability to add complexity in the future.**

## Top features

* Deployment of Splunk Enterprise that can be run on your laptop or desktop, or pushed to a large orchestrator
* Support for multiple Splunk Enterprise topologies including:
    * Standalone Splunk Enterprise server
    * Standalone Universal and Heavy forwarders
    * See [Splunk Validated Architectures](https://www.splunk.com/pdfs/white-papers/splunk-validated-architectures.pdf) for more information. Currently, only the S1 architecture is supported.
* Automatic installation of the latest version of Splunk Enterprise and the Splunk Universal Forwarder, beginning with version 7.2
    * Defaults to the latest official Splunk Enterprise/Splunk Universal Forwarder release
    * **Versions 7.2 and higher** can be installed and upgraded to the latest version of Splunk Enterprise and the Splunk Universal Forwarder.
* Automatic installation of most Splunk-supported apps
	* Splunk Enterprise applications such as Splunk IT Service Intelligence (ITSI) and Splunk Enterprise Security (ES) might require additional setup and must be installed by Splunk Professional Services.
