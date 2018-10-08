### Introduction to Splunk Enterprise inside Containers ###
This documentation provides a good primer on containers, and why you may want to use them in your environment.  Additional information can be 
found at [Docker](https://www.docker.com/resources/what-container).

##### The Need for Containers #####
Splunk Enterprise is most commonly deployed with dedicated hardware, and in configurations to support the size of your organization.
Expanding your Splunk Enterprise service using only dedicated hardware involves procuring new hardware, installing the operating system,
installing and then configuring Splunk Enterprise. Expanding to meet the needs of your users rapidly becomes difficult, and overly complex, in
this model. The overhead of this operation normally leads people down the path of creating virtual machines
using a hypervisor. Using a hypervisor provides a significant improvement to the speed of spinning up a new deployment, but comes with
one major drawback:  the overhead of running multiple operating systems on one host.

<img src="container-vm-whatcontainer_2.png" width="370"/><img src="docker-containerized-appliction-blue-border_2.png" width="370"/>

###### source:[Docker](https://www.docker.com) ######

Containers allow the application to be the only thing that runs in a "vm like" isolated environment. Unlike a hypervisor, the container-based system does not need to start the guest operating system. The lack of guest operating system
allows a single host to dedicate more resources towards the application. The community has asked Splunk for container support, to provide the rich functionality Splunk Enterprise offers for dedicated hardware deployments. This project delivers on that request.

##### History #####
In 2015, Denis Gladkikh (@outcoldman) created in his spare time an open-source GitHub repository for installing Splunk Enterprise, Splunk Universal Forwarder and Splunk Light inside containers.
In 2016 Denis Gladkikh transitioned ownership of Splunk Docker Image to Splunk, announcement was made at .conf16.
Universal Forwarders and standalone instances
were being brought online at a rapid pace, which introduced a new level of complexity into the enterprise environment. 
In 2018, a new container image was created to improve the flexibility with which Splunk Enterprise could be operated in larger and more dynamic environments.
Splunk's new container can now start with a small environment and grow with the deployment. This however has caused a divergence
from the open-source community edition of the Splunk Enterprise container. As a result, containers for Splunk Enterprise versions prior to 7.1 can not 
be used with, or in conjunction with, this new version as it is not backward compatible. 
We are also unable to support version updates from any prior container to the current version released with Splunk Enterprise and Splunk Universal Forwarder 7.2, as the older versions are not forward compatible. 
We are sorry for any inconvenience this may cause. 

