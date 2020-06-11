## Installing Splunk Apps and Add-ons
The Splunk Docker image supports the ability to dynamically install any Splunk-compliant app or add-on. These can be certified apps that are hosted through [SplunkBase](https://splunkbase.splunk.com/) or they might be local apps you have developed yourself.

App installation can be done a variety of ways: either through a file/directory volume-mounted inside the container, or through an external URL for dynamic downloads. Nothing is required for the former, and the environment variable `SPLUNK_APPS_URL` supports the latter.

**NOTE:** Installation of Splunk Enterprise Security (ES) and Splunk IT Service Intelligence (ITSI) is currently not supported with this image. Please contact Splunk Services for more information on using these applications with Splunk Enterprise in a container.

## Navigation

* [Volume-mount app directory](#volume-mount-app-directory)
* [Download via URL](#download-via-url)
* [Multiple apps](#multiple-apps)
* [Apps in distributed environments](#apps-in-distributed-environments)

## Volume-mount app directory
If you have a local directory that follows the proper Splunk apps model, you can mount this entire path to the container at runtime.

For instance, take the following app `splunk_app_example`:
```bash
$ find . -type f
./splunk_app_example/default/app.conf
./splunk_app_example/metadata/default.meta
```

We can bind-mount this upon container start and use it as a regular Splunk app:
```bash
# Volume-mounting option using --volumes/-v flag
$ docker run -it -v "$(pwd)/splunk_app_example:/opt/splunk/etc/apps/splunk_app_example/" --name so1 --hostname so1 -p 8000:8000 -e "SPLUNK_PASSWORD=<password>" -e "SPLUNK_START_ARGS=--accept-license" -it splunk/splunk:latest

# Volume-mounting option using --mount flag
$ docker run -it --mount type=bind,source="$(pwd)"/splunk_app_example,target=/opt/splunk/etc/apps/splunk_app_example/ --name so1 --hostname so1 -p 8000:8000 -e "SPLUNK_PASSWORD=<password>" -e "SPLUNK_START_ARGS=--accept-license" -it splunk/splunk:latest
```

You should be able to view the `splunk_app_example` in SplunkWeb after the container successfully finished provisioning.

## Download via URL
In most cases, you're likely hosting the app as a tar file somewhere accessible in your network. This decouples the need for Splunk apps and configuration files to exist locally on a node, which enables Splunk to run in a container orchestration environment.

#### SplunkBase apps
Please refer to this docker-compose.yml file for how to download SplunkBase apps with authentication:

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_APPS_URL=https://splunkbase.splunk.com/app/2890/release/4.1.0/download
      - SPLUNKBASE_USERNAME=<sb-username>
      - SPLUNKBASE_PASSWORD=<sb-password>
      - SPLUNK_PASSWORD=<password>
    ports:
      - 8000
```

#### Self-hosted apps
Please refer to this docker-compose.yml file for how to download any app hosted at an arbitrary location:

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_APPS_URL=https://webserver/apps/app.spl
      - SPLUNK_PASSWORD=<password>
    ports:
      - 8000
```

#### Apps on filesystem
If you build your own image on top of the `splunk/splunk` or `splunk/universalforwarder` image, it's possible you may embed a tar file of an app inside. Or, you can go with the bind-mount volume approach and inject a tar file on container run time. In either case, it's still possible to install an app from this file on the container's filesystem with the following.

Please refer to this docker-compose.yml file for how to install an app in the container's filesystem:

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_APPS_URL=/tmp/app.tgz
      - SPLUNK_PASSWORD=<password>
    ports:
      - 8000
```

## Multiple apps
As one would expect, Splunk can and should support downloading any combination or series of apps. This can be incredibly useful when cross-referencing data from various sources.

The `SPLUNK_APPS_URL` supports multiple apps, as long as they are comma-separated. Refer to this `docker-compose.yml` file for how to install multiple apps:

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_APPS_URL=/tmp/app.tgz,https://webserver/apps/app.spl,https://splunkbase.splunk.com/app/2890/release/4.1.0/download
      - SPLUNKBASE_USERNAME=<sb-username>
      - SPLUNKBASE_PASSWORD=<sb-password>
      - SPLUNK_PASSWORD=<password>
    ports:
      - 8000
```

## Apps in distributed environments
This docker image also deploys apps when running Splunk in distributed environments. There are, however, special cases and instructions for how apps get deployed in these scenarios.

In the case of multiple search heads (no clustering) and multiple indexers (no clustering), you will explicitly need to tell each container what apps to install by defining a `SPLUNK_APPS_URL` for each role. See the example below and note the different apps used for search heads and indexers:

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  sh1:
    networks:
      splunknet:
        aliases:
          - sh1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: sh1
    container_name: sh1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh1,sh2
      - SPLUNK_ROLE=splunk_search_head
      - SPLUNK_APPS_URL=https://webserver/apps/appA.tgz
      - SPLUNK_PASSWORD
    ports:
      - 8000

  sh2:
    networks:
      splunknet:
        aliases:
          - sh2
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: sh2
    container_name: sh2
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh1,sh2
      - SPLUNK_ROLE=splunk_search_head
      - SPLUNK_APPS_URL=https://webserver/apps/appA.tgz
      - SPLUNK_PASSWORD
    ports:
      - 8000

  idx1:
    networks:
      splunknet:
        aliases:
          - idx1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx1
    container_name: idx1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh1,sh2
      - SPLUNK_ROLE=splunk_indexer
      - SPLUNK_APPS_URL=https://webserver/apps/appB.tgz,https://webserver/apps/appC.tgz
      - SPLUNK_PASSWORD
    ports:
      - 8000

  idx2:
    networks:
      splunknet:
        aliases:
          - idx2
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx2
    container_name: idx2
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh1,sh2
      - SPLUNK_ROLE=splunk_indexer
      - SPLUNK_APPS_URL=https://webserver/apps/appB.tgz,https://webserver/apps/appC.tgz
      - SPLUNK_PASSWORD
    ports:
      - 8000
```

In the case of search head clusters, you will explicitly need to tell the `splunk_deployer` what apps to install by defining a `SPLUNK_APPS_URL` for that particular role. The deployer will manage the distribution of apps to each of the search head cluster members (search heads). See the example below and note the different apps used for search heads and indexers:


```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  dep1:
    networks:
      splunknet:
        aliases:
          - dep1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: dep1
    container_name: dep1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_ROLE=splunk_deployer
      - SPLUNK_APPS_URL=https://webserver/apps/appA.tgz,https://webserver/apps/appB.tgz
    ports:
      - 8000

  sh1:
    networks:
      splunknet:
        aliases:
          - sh1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: sh1
    container_name: sh1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_ROLE=splunk_search_head_captain
    ports:
      - 8000

  sh2:
    networks:
      splunknet:
        aliases:
          - sh2
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: sh2
    container_name: sh2
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_ROLE=splunk_search_head
    ports:
      - 8000

  sh3:
    networks:
      splunknet:
        aliases:
          - sh3
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: sh3
    container_name: sh3
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_ROLE=splunk_search_head
    ports:
      - 8000

  idx1:
    networks:
      splunknet:
        aliases:
          - idx1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx1
    container_name: idx1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_ROLE=splunk_indexer
    ports:
      - 8000

  idx2:
    networks:
      splunknet:
        aliases:
          - idx2
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx2
    container_name: idx2
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_ROLE=splunk_indexer
    ports:
      - 8000
```

In the case of indexer clusters, you will explicitly need to tell the `splunk_cluster_master` what apps to install by defining a `SPLUNK_APPS_URL` for that particular role. The cluster master will manage the distribution of apps to each of the indexer cluster members (indexers). See the example below and note the different apps used for search heads and indexers:

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  sh1:
    networks:
      splunknet:
        aliases:
          - sh1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: sh1
    container_name: sh1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2,idx3
      - SPLUNK_SEARCH_HEAD_URL=sh1
      - SPLUNK_CLUSTER_MASTER_URL=cm1
      - SPLUNK_ROLE=splunk_search_head
      - SPLUNK_PASSWORD
    ports:
      - 8000

  cm1:
    networks:
      splunknet:
        aliases:
          - cm1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: cm1
    container_name: cm1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2,idx3
      - SPLUNK_SEARCH_HEAD_URL=sh1
      - SPLUNK_CLUSTER_MASTER_URL=cm1
      - SPLUNK_ROLE=splunk_cluster_master
      - SPLUNK_APPS_URL=https://webserver/apps/appA.tgz,https://webserver/apps/appB.tgz
      - SPLUNK_PASSWORD
    ports:
      - 8000

  idx1:
    networks:
      splunknet:
        aliases:
          - idx1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx1
    container_name: idx1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2,idx3
      - SPLUNK_SEARCH_HEAD_URL=sh1
      - SPLUNK_CLUSTER_MASTER_URL=cm1
      - SPLUNK_ROLE=splunk_indexer
      - SPLUNK_PASSWORD
    ports:
      - 8000

  idx2:
    networks:
      splunknet:
        aliases:
          - idx2
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx2
    container_name: idx2
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2,idx3
      - SPLUNK_SEARCH_HEAD_URL=sh1
      - SPLUNK_CLUSTER_MASTER_URL=cm1
      - SPLUNK_ROLE=splunk_indexer
      - SPLUNK_PASSWORD
    ports:
      - 8000

  idx3:
    networks:
      splunknet:
        aliases:
          - idx3
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: idx3
    container_name: idx3
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2,idx3
      - SPLUNK_SEARCH_HEAD_URL=sh1,sh2,sh3
      - SPLUNK_CLUSTER_MASTER_URL=cm1
      - SPLUNK_ROLE=splunk_indexer
      - SPLUNK_PASSWORD
    ports:
      - 8000
```
