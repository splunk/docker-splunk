### Installing a Splunk Enterprise License ###
This document will cover the different methods used to install the Splunk Enterprise License. Before using this document
please contact Splunk to acquire a Splunk Enterprise License.

There are two different ways to pass in a license file in when the container starts. This can be either through a directory mounted inside of the container, or through an external URL that the container can download the license file into. The parameter SPLUNK_LICENSE_URI supports both methods of license install.

#### Using a Splunk Enterprise License using Docker Engine Swarm ####
We recommend using Docker Secrets to manage your license. More information on Docker Secrets can be found on [Docker's website](https://docs.docker.com/engine/swarm/secrets/). These instructions will cover the general method to mount the secrets into the container.

##### Step 1: Create the secret #####
The first step will be to create a secret using your existing license file. This can be done by first connecting to docker swarm and then running the following command.
```
docker secret create splunk_license path/to/license.lic
```
where license.lic is the splunk license.

##### Step 2: Define the service #####
The next step is to create the service to use the secret. For example, the following service uses the docker-compose syntax to create a single instance that consumes the secret. We'll create a file called splunk-stack.yml with the following contents:

```
version: "3.1"

networks:
  splunknet:
    driver: overlay 

services:
  so1:
    networks:
      splunknet:
        aliases:
          - so1
    image: splunk-debian-9:latest 
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_LICENSE_URI=/run/secrets/splunk_license
    ports:
      - 8000
      - 8089
    secrets:
      - splunk_license
secrets:
    splunk_license:
        external: true
```

These contents define our service as a single stand alone container that will load the license from the location /run/secrets/splunk_license. By default, the Docker Engine will mount the splunk_license secret into /run/secrets, but you can configure this to be a different location. See the Docker Secret documentation for more detail.

##### Step 3: Start the service #####

To start the service, run the following command 
```
docker stack deploy --compose-file=splunk-stack.yaml splunk_deployment
```

On the console output you should see the play execute and finish running. From there, you should be able to locate the the service by using the command

##### Step 4: Verify the results #####
To inspect the service, you should be able to run the following command. 
```
docker service ls --filter name=splunk_deployment_so1
```
This will display the port mappings needed to connect to the splunk instance.

