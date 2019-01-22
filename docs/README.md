# Splunk Enterprise Docker Container

**Splunk's Docker container for Splunk Enterprise and Splunk Universal Forwarder are designed to help first-time users quickly deploy and gain hands-on experience with the Splunk software, while still allowing for complex deployments in the future**

## Top Features

* Deployment of Splunk Enterprise that can be run on your laptop or desktop, or pushed to a large orchestrator
* Support for multiple Splunk Enterprise topologies including:
    * Standalone Splunk Enterprise server
    * Standalone Universal and Heavy forwarders
    * See [Splunk Validated Architectures](https://www.splunk.com/pdfs/white-papers/splunk-validated-architectures.pdf) for more information.  Currently only the S1 architecture is supported, with new architectures following soon.
* Automatic installation of all upcoming versions of Splunk Enterprise / Splunk Universal Forwarder (beginning with version 7.2)
    * Defaults to the latest official Splunk Enterprise/Splunk Universal Forwarder release
    * Previously released versions can be installed and upgraded to the most current version of Splunk Enterprise / Splunk Universal Forwarder. However, Splunk versions prior to 7.2 are not supported.
* Automatic installation of most Splunk-supported apps
	* **Note:** Enterprise applications such as Splunk IT Service Intelligence (ITSI) and Splunk Enterprise Security (ES) may require additional setup and must be installed by Splunk Professional Services.
