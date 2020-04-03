## Using a Deployment Server
One role the Splunk Docker image can assume is the `splunk_deployment_server`. This is generally a standalone instance that manages configurations and applications across unclustered/unsynchronized members of your deployment. For more detailed information, please see the [architectural overview on the deployment server](https://docs.splunk.com/Documentation/Splunk/latest/Updating/Deploymentserverarchitecture).

This is particularly helpful and useful in the case of running multiple standalones or forwarders (both universal and heavy forwarders). When running a fleet of isolated Splunk containers, it can be a chore to wrangle configurations and maintain consensus so that each instance is provisioned identically. This can be solved with the addition of the deployment server - when added to your environment, all non-clustered Splunk roles can register with it to periodically fetch content and maintain a stateful setup.

**NOTE:** Installation of Splunk Enterprise Security (ES) and Splunk IT Service Intelligence (ITSI) is currently not supported with this image. Please contact Splunk Services for more information on using these applications with Splunk Enterprise in a container.

## Navigation

* [Examples](#examples)
    * [Create standalone and deployment server](#create-standalone-and-deployment-server)
    * [Create heavy forwarder and deployment server](#create-heavy-forwarder-and-deployment-server)
    * [Create universal forwarder and deployment server](#create-universal-forwarder-and-deployment-server)
* [Role-based distribution](#multiple-deployment-servers)

## Examples

#### Create standalone and deployment server
The following will allow you spin up a forwarder, and register it with the deployment server located at `SPLUNK_DEPLOYMENT_SERVER`, or in this case `depserver1`. The deployment server will fetch the app from `SPLUNK_APPS_URL` and proceed to distribute it to your standalone.

<details><summary>docker-compose.yml</summary><p>

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  so1:
    networks:
      splunknet:
        aliases:
          - so1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    container_name: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_DEPLOYMENT_SERVER=depserver1
      - SPLUNK_PASSWORD
    ports:
      - 8000

  depserver1:
    networks:
      splunknet:
        aliases:
          - depserver1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: depserver1
    container_name: depserver1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_deployment_server
      - SPLUNK_APPS_URL=https://artifact.company.internal/splunk_app.tgz
      - SPLUNK_PASSWORD
```
</p></details>

Execute the following to bring up your deployment:
```
$ SPLUNK_PASSWORD=<password> docker-compose up -d
```

#### Create heavy forwarder and deployment server
The following will allow you spin up a forwarder, and stream its logs to an independent, external indexer located at `idx1-splunk.company.internal`, as long as that hostname is reachable on your network. Additionally, it brings up a deployment server, which will download an app and distribute it to the heavy forwarder.

<details><summary>docker-compose.yml</summary><p>

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  hf1:
    networks:
      splunknet:
        aliases:
          - hf1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: hf1
    container_name: hf1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_heavy_forwarder
      - SPLUNK_INDEXER_URL=idx1-splunk.company.internal
      - SPLUNK_DEPLOYMENT_SERVER=depserver1
      - SPLUNK_ADD=tcp 1514
      - SPLUNK_PASSWORD
    ports:
      - 1514

  depserver1:
    networks:
      splunknet:
        aliases:
          - depserver1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: depserver1
    container_name: depserver1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_deployment_server
      - SPLUNK_APPS_URL=https://artifact.company.internal/splunk_app.tgz
      - SPLUNK_PASSWORD
```
</p></details>

Execute the following to bring up your deployment:
```
$ SPLUNK_PASSWORD=<password> docker-compose up -d
```

#### Create universal forwarder and deployment server
The following will allow you spin up a universal forwarder, and stream its logs to an independent, external indexer located at `idx1-splunk.company.internal`, as long as that hostname is reachable on your network. Additionally, it brings up a deployment server, which will download an app and distribute it to the universal forwarder.

<details><summary>docker-compose.yml</summary><p>

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  uf1:
    networks:
      splunknet:
        aliases:
          - uf1
    image: ${UF_IMAGE:-splunk/universalforwarder:latest}
    hostname: uf1
    container_name: uf1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1-splunk.company.internal
      - SPLUNK_DEPLOYMENT_SERVER=depserver1
      - SPLUNK_ADD=tcp 1514
      - SPLUNK_PASSWORD
    ports:
      - 1514

  depserver1:
    networks:
      splunknet:
        aliases:
          - depserver1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: depserver1
    container_name: depserver1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_deployment_server
      - SPLUNK_APPS_URL=https://artifact.company.internal/splunk_app.tgz
      - SPLUNK_PASSWORD
```
</p></details>

Execute the following to bring up your deployment:
```
$ SPLUNK_PASSWORD=<password> docker-compose up -d
```

## Role-based distribution
When using the `SPLUNK_DEPLOYMENT_SERVER` environment variable on a specific container (or set of containers), it instructs the bootstrap process to register itself with the deployment server. That particular deployment server will then proceed to push all apps located in `${SPLUNK_HOME}/etc/deployment-apps/` to all of its clients.

If you plan on using an external deployment server, it's possible to specify [server classes](https://docs.splunk.com/Documentation/Splunk/latest/Updating/Definedeploymentclasses) to determine which configurations/apps are pushed to which clients. By default, the deployment server stood up using this Docker image will default to pushing its apps and configurations to *all* clients that register against it. If you wish to define groupings within the deployment server container, please see the section on defining a [custom config file](../ADVANCED.md#create-custom-configs) to define the `serverclass.conf`.

Having said that, because the deployment server is a fairly lightweight role and containers are cheap to create, it is entirely possible to use multiple deployment servers to achieve the same effect as group-based bundle deployments. See the following example to show how different deployment servers are created to manage different roles (standalones and heavy forwarders).

<details><summary>docker-compose.yml</summary><p>

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  so1:
    networks:
      splunknet:
        aliases:
          - so1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    container_name: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_DEPLOYMENT_SERVER=ds-1
      - SPLUNK_PASSWORD
    ports:
      - 8000

  hf1:
    networks:
      splunknet:
        aliases:
          - hf1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: hf1
    container_name: hf1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_heavy_forwarder
      - SPLUNK_STANDALONE_URL=so1
      - SPLUNK_DEPLOYMENT_SERVER=ds-2
      - SPLUNK_ADD=tcp 1514
      - SPLUNK_PASSWORD
    ports:
      - 1514

  ds-1:
    networks:
      splunknet:
        aliases:
          - ds-1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: ds-1
    container_name: ds-1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_deployment_server
      - SPLUNK_APPS_URL=https://artifact.company.internal/splunk_app_for_standalone.tgz
      - SPLUNK_PASSWORD

  ds-2:
    networks:
      splunknet:
        aliases:
          - ds-2
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: ds-2
    container_name: ds-2
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_ROLE=splunk_deployment_server
      - SPLUNK_APPS_URL=https://artifact.company.internal/splunk_app_for_forwarder.tgz
      - SPLUNK_PASSWORD
```
</p></details>

Execute the following to bring up your deployment:
```
$ SPLUNK_PASSWORD=<password> docker-compose up -d
```
