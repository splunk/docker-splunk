## Data Storage ##
This section will cover examples of different options for configuring data persistance. This includes both indexed data and 
configuration items. Splunk does not officially support data persistence in container environments. The following are 
intended as examples and unofficial guidelines. 

### Storing indexes and search artifacts ###
Splunk Enterprise, by default, Splunk Enterprise uses the var directory for indexes, search artifacts, etc. In the public image, the Splunk Enterprise 
home directory is /opt/splunk, and the indexes are configured to run under var/. If you want to persist the indexed 
data, then mount an external directory into the container under this folder.

If you do not want to modify or persist any configuration changes made outside of what has been defined in the docker 
image file, then use the following steps for your service.

#### Step 1: Create a named volume ####
To create a simple named volume in your Docker environment, run the following command
```
docker volume create so1-var
```
See Docker's official documentation for more complete instructions and additional options.

#### Step 2: Define the docker compose YAML  and start the service####
Using the Docker Compose format, save the following contents into a docker-compose.yml file

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

volumes:
  so1-var:

services:
  so1:
    networks:
      splunknet:
        aliases:
          - so1
    image: splunk-debian-9:latest
    container_name: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_PASSWORD=changem3N0w!
      - DEBUG=true
    ports:
      - 8000
      - 8089
    volumes:
      - so1-var:/opt/splunk/var
```

This mounts only the contents of /opt/splunk/var, so anything outside of this folder will not persist. Any configuration changes will not 
remain when the container exits.  Note that changes will persist between starting and stopping a container. See 
Docker's documentation for more discussion on the difference between starting, stopping, and exiting if the difference
between them is unclear.

In the same directory as docker-compose.yml run the following command
```
docker-compose up
```
to start the service.

#### Viewing the contents of the volume ####
To view the data outside of the container run
```
docker volume inspect so1-var
```
The output of that command should list where the data is stored.

### Storing indexes, search artifacts, and configuration changes ###
In this section, we build off of the previous example to save the configuration as well. This can make it easier to save modified 
configurations, but simultaneously allows configuration drift to occur. If you want to keep configuration drift from 
happening, but still want to be able to persist some of the data, you can save off the specific "local" folders that 
you want the data to be persisted for (such as etc/system/local). However, be careful when doing this because you will 
both know what folders you need to save off and the number of volumes can proliferate rapidly - depending on the 
deployment. Please take the "Administrating Splunk" through Splunk Education prior to attempting this configuration.

In these examples, we will assume that the entire etc folder is being mounted into the container.

#### Step 1: Create a named volume ####
Again, create a simple named volume in your Docker environment, run the following command
```
docker volume create so1-etc
```
See Docker's official documentation for more complete instructions and additional options.

#### Step 2: Define the docker compose YAML ####
Notice that this differs from the previous example by adding in the so1-etc volume references.
In the following example, save the following data into a file named docker-compose.yml

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

volumes:
  so1-var:
  so1-etc:

services:
  so1:
    networks:
      splunknet:
        aliases:
          - so1
    image: splunk-debian-9:latest
    container_name: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_PASSWORD=<password>
      - DEBUG=true
    ports:
      - 8000
      - 8089
    volumes:
      - so1-var:/opt/splunk/var
	  - so1-etc:/opt/splunk/etc
```

In the directory where the docker-compose.yml file is saved, run 
```
docker-compose up
```
to start the service.

When the volume is mounted the data will persist after the container exits. If a container has exited and restarted, 
but no data shows up, then check the volume definition and verify that the container did not create a new volume 
or that the volume mounted is in the same location. 

#### Viewing the contents of the volume ####
To view the etc directory outside of the container run one or both of the commands
```
docker volume inspect so1-etc
```
The output of that command should list the directory associated with the volume mount.

#### Upgrading the container ####
Currently upgrading a container is not officially supported. Contact Splunk Support if you have any questions.

#### Volume Mount Guidelines ####
**Do not mount the same folder into two different Splunk Enterprise instances, this can cause inconsistencies in the 
indexed data and undefined behavior within Splunk Enterprise itself.**
