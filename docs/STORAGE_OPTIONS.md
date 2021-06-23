## Data Storage ##
This section will cover examples of different options for configuring data persistence. This includes both indexed data and configuration items. Splunk only supports data persistence to volumes mounted outside of the container. Data persistence for folders inside of the container is not supported. The following are intended only as examples and unofficial guidelines.

### Storing indexes and search artifacts ###
By default, Splunk Enterprise uses the var directory for indexes, search artifacts, etc. In the public image, the Splunk Enterprise home directory is /opt/splunk, and the indexes are configured to run under var/. If you want to persist the indexed data, then mount an external directory into the container under this folder.

If you do not want to modify or persist any configuration changes made outside of what has been defined in the docker image file, then use the following steps for your service.

#### Step 1: Create a named volume ####
To create a simple named volume in your Docker environment, run the following command
```
docker volume create so1-var
```
See Docker's official documentation for more complete instructions and additional options.

#### Step 2: Define the docker-compose YAML  and start the service ####
Using the Docker Compose format, save the following contents into a docker-compose.yml file:

```yaml
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

This mounts only the contents of /opt/splunk/var, so anything outside this folder will not persist. Any configuration changes will not remain when the container exits. Note that changes will persist between starting and stopping a container. See the Docker documentation for more discussion on the difference between starting, stopping, and exiting if the difference between them is unclear.

In the same directory as `docker-compose.yml`, run the following command to start the service.
```
docker-compose up
```

#### Viewing the contents of the volume ####
To view the data outside of the container run:
```
docker volume inspect so1-var
```
The output of that command should list where the data is stored.

### Storing indexes, search artifacts, and configuration changes ###
In this section, we build off of the previous example to save the configuration as well. This can make it easier to save modified configurations, but simultaneously allows configuration drift to occur. If you want to keep configuration drift from happening, but still want to persist some of the data, you can save off the specific "local" folders that you want the data to be persisted for (such as etc/system/local). However, be careful when doing this because you will both know what folders you need to save off and the number of volumes can increase rapidly - depending on the deployment. Please take the "Administrating Splunk" through Splunk Education before attempting this configuration.

We will assume that the entire /etc folder is being mounted into the container in these examples.

#### Step 1: Create a named volume ####
Again, create a simple named volume in your Docker environment, run the following command
```shell
docker volume create so1-etc
```
See Docker's official documentation for more complete instructions and additional options.

#### Step 2: Define the Docker Compose YAML ####
Notice that this differs from the previous example by adding in the so1-etc volume references. In the following example, save the following data into a file named `docker-compose.yml`.

```yaml
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

In the same directory as `docker-compose.yml`, run the following command to start the service:
```shell
docker-compose up
```

When the volume is mounted, the data will persist after the container exits. If a container has exited and restarted, but no data shows up, check the volume definition and verify that the container did not create a new volume or that the volume mounted is in the same location.

#### Viewing the contents of the volume ####
To view the /etc directory outside of the container, run one or both of the commands
```shell
docker volume inspect so1-etc
```
The output of that command should list the directory associated with the volume mount.

#### Volume Mount Guidelines ####
Do not mount the same folder into two different Splunk Enterprise instances. This can cause inconsistencies in the indexed data and undefined behavior within Splunk Enterprise itself.

### Upgrading Splunk instances in your containers ###
Upgrading Splunk instances requires volumes to be mounted for /opt/splunk/var and /opt/splunk/etc.

#### Step 1: Persist your /opt/splunk/var and /opt/splunk/etc ####
Follow the named volume creation tutorial above in order to have /opt/splunk/var and /opt/splunk/etc mounted for persisting data.

#### Step 2: Update your yaml file with a new image and SPLUNK_UPGRADE=true ####
In the same yaml file you initially used to deploy Splunk instances, update the specified image to the next version of Splunk image. Then, set `SPLUNK_UPGRADE=true` in the environment of all containers you wish to upgrade. Make sure to state relevant named volumes so persisted data can be mounted to a new container.

Below is an example yaml with `SPLUNK_UPGRADE=true`:

```yaml
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
    image: <NEXT_VERSION_SPLUNK_IMAGE>
    container_name: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_PASSWORD=<password>
      - DEBUG=true
      - SPLUNK_UPGRADE=true
    ports:
      - 8000
      - 8089
    volumes:
      - so1-var:/opt/splunk/var
      - so1-etc:/opt/splunk/etc
```

#### Step 3: Deploy your containers using the updated yaml ####
Like how you initially deployed your containers, run the command with the updated yaml containing a reference to the new image and SPLUNK_UPGRADE=true in the environment. Make sure that you do NOT destroy previously existing networks and volumes. After running the command with the yaml file, your containers should be recreated with the new version of Splunk and persisted data properly mounted to /opt/splunk/var and /opt/splunk/etc.

#### Different types of volumes ####
Using named volume is recommended because it is easier to attach and detach volumes to different Splunk instances while persisting your data. If you use anonymous volumes, Docker gives them random and unique names so you can still reuse anonymous volumes on other containers. If you use bind mounts, make sure that the mounts are set up correctly to persist /opt/splunk/var and opt/splunk/etc. Starting new containers without proper mounts will result in a loss of your data.

See [Create and manage volumes](https://docs.docker.com/storage/volumes/#create-and-manage-volumes) in the Docker documentation for more information.
