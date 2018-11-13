## Advanced Usage ##
This section shows several of the advanced functions of the container, as well as how to build a container
from the github repo.  
** Note: ** Not all sections below will leave your container in a supported state. See `documentation/SETUP.md` for the list of officially supported configurations. 

##### Building From Source (Unsupported) #####
1. Download the Splunk Docker GitHub repository to your local development environment:
```
git clone https://github.com/splunk/docker-splunk
```
The supplied `Makefile` located inside the root of the project provides the ability to download any of the remaining
components. 

** WARNING:** Modifications to the "base" image may result in Splunk being unable to start or run correctly.

3. To complete the creation of the `splunk:latest` image, run the following in the project root directory:
```
make splunk
```

## Advanced Configurations ##
Splunk's Docker container has several functions that can be configured. These options are specified by either supplying a `default.yml` file or
by passing in environment variables. Below is a list of environment variables that may/must be used when starting the docker container. 

#### Valid Enterprise Environment Variables
| Environment Variable Name | Description | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|
| SPLUNK_BUILD_URL | URL to Splunk build where we can fetch a Splunk build to install | no | no | no |
| SPLUNK_DEFAULTS_URL | default.yml URL | no | no | no |
| SPLUNK_UPGRADE | If this is True, we won’t run any provisioning after installation. Use this to upgrade and redeploy containers with a newer version of Splunk. | no | no | no |
| SPLUNK_ROLE | Specify the container’s current Splunk Enterprise role. Supported Roles: splunk_standalone, splunk_indexer, splunk_deployer, splunk_search_head, etc. | no | yes | yes |
| DEBUG | Print Ansible vars to stdout (supports Docker logging) | no | no | no |
| SPLUNK_START_ARGS | Accept the license with “—accept-license”. Please note, we will not start a container without the existence of --accept-license in this variable. | yes | yes | yes |
| SPLUNK_LICENSE_URI | URI we can fetch a Splunk Enterprise license. This can be a local path or a remote URL. | no | no | no |
| SPLUNK_STANDALONE_URL | List of all Splunk Enterprise standalone hosts (network alias) separated by comma | no | no | no |
| SPLUNK_SEARCH_HEAD_URL | List of all Splunk Enterprise search head hosts (network alias) separated by comma | no | yes | yes |
| SPLUNK_INDEXER_URL| List of all Splunk Enterprise indexer hosts (network alias) separated by comma | no | yes | yes |
| SPLUNK_HEAVY_FORWARDER_URL | List of all Splunk Enterprise heavy forwarder hosts (network alias) separated by comma | no |  no | no |
| SPLUNK_DEPLOYER_URL | One Splunk Enterprise deployer host (network alias) | no | yes | no |
| SPLUNK_CLUSTER_MASTER_URL | One Splunk Enterprise cluster master host (network alias) | no | no | yes |
| SPLUNK_SEARCH_HEAD_CAPTAIN_URL | One Splunk Enterprise search head host (network alias). Passing this ENV variable will enable search head clustering. | no | yes | no |
| SPLUNK_S2S_PORT | Default Forwarding Port | no | no | no |
| SPLUNK_SVC_PORT | Default Admin Port | no | no | no |
| SPLUNK_PASSWORD* | Default password of the admin user| yes | yes | yes |
| SPLUNK_HEC_TOKEN | HEC (HTTP Event Collector) Token when enabled | no | no | no |
| SPLUNK_SHC_SECRET | Search Head Clustering Shared secret | no | yes | no |
| SPLUNK_IDXC_SECRET | Indexer Clustering Shared Secret | no | no | yes |
| NO_HEALTHCHECK | Disable the Splunk healthcheck script | no | no | yes |

* Password must be set either in default.yml or as the environment variable `SPLUNK_PASSWORD`

#### Valid Universal Forwarder Environment Variables
|Environment Variable Name| Description | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|
| SPLUNK_DEPLOYMENT_SERVER | One Splunk host (network alias) that we use as a deployment server. (http://docs.Splunk.com/Documentation/Splunk/latest/Updating/Configuredeploymentclients) | no | no | no |
| SPLUNK_ADD | List of items to add to monitoring separated by comma. Example, SPLUNK_ADD=udp 1514,monitor /var/log/*. This will monitor udp 1514 port and /var/log/* files. | no | no | no |
| SPLUNK_BEFORE_START_CMD | List of commands to run before Splunk starts separated by comma. Ansible will run “{{splunk.exec}} {{item}}”. | no | no | no |
| SPLUNK_CMD | List of commands to run after Splunk starts separated by comma. Ansible will run “{{splunk.exec}} {{item}}”. | no | no | no |
| DOCKER_MONITORING | True or False. This will install Docker monitoring apps. | no | no | no |

#### default.yml valid options
`default.yml` exposes several additional options for configuring Splunk, and may be set by either mounting a volume to `/tmp/defaults` or by setting the
`SPLUNK_DEFAULTS_URL` environment token. A sample `default.yml` file can be generated by following the instructions [here](#generating-a-defaultyml-file).

Root items influence the behavior of everything in the container; they have global scope inside the container.
Example:
```
    ---
    retry_num: 100
```

|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
| retry_num | Default number of loop attempts to connect containers | none | 100 | yes | yes | yes |

The major object "splunk" in the YAML file will contain variables that influence how Splunk operates. Example:
```
    Splunk:
        opt: /opt
        home: /opt/splunk
        user: splunk
        group: splunk
        exec: /opt/splunk/bin/splunk
        pid: /opt/splunk/var/run/splunk/splunkd.pid
        password: "{{ splunk_password | default(<password>) }}"
        svc_port: 8089
        s2s_port: 9997
        http_port: 8000
        hec_port: 8088
        hec_disabled: 0
        hec_enableSSL: 1
        #The hec_token here is used for INGESTION only. By that I mean receiving Splunk events.
        #Setting up your environment to forward events out of the cluster is another matter entirely
        hec_token: <default_hec_token>
```

|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
|opt| Parent directory where Splunk is running | splunk | /opt | yes | yes | yes |
|home| Location of the Splunk Installation | splunk | /opt/splunk | yes | yes | yes |
|user| Operating System User to Run Splunk Enterprise As | splunk | splunk | yes | yes | yes |
|group| Operating System Group to Run Splunk Enterprise As | splunk | splunk | yes | yes | yes |
|exec| Path to the Splunk Binary | splunk | /opt/splunk/bin/splunk | yes | yes | yes |
|pid| Location to the Running PID File | splunk | /opt/splunk/var/run/splunk/splunkd.pid | yes | yes | yes
|password| Password for the admin account | splunk | **none** | yes | yes | yes |
|svc_port| Default Admin Port | splunk | 8089 | yes | yes | yes |
|s2s_port| Default Forwarding Port | splunk | 9997 | yes | yes | yes |
|http_port| Default SplunkWeb Port | splunk | 8000 | yes | yes | yes |
|hec_port| Default HEC Input Port | splunk | 8088 | no | no | no |
|hec_disabled| Enable / Disable HEC | splunk | 0 | no | no | no |
|hec_enableSSL| Force HEC to use encryption | splunk | 1 | no | no | no |
|hec_token| Token to enable for HEC inputs | splunk | **none** | no | no | no |

The app_paths section is located as part of the "splunk" parent object. The settings located in this section will directly influence how apps are installed inside the container. Example:
```
        app_paths:
            default: /opt/splunk/etc/apps
            shc: /opt/splunk/etc/shcluster/apps
            idxc: /opt/splunk/etc/master-apps
            httpinput: /opt/splunk/etc/apps/Splunk_httpinput
```

|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
|default| Normal apps for standalone instances will be installed in this location | splunk.app_paths | **none** | no | no | no |
|shc| Apps for search head cluster instances will be installed in this location (usually only done on the deployer)| splunk.app_paths | **none** | no | no | no |
|idxc| Apps for index cluster instances will be installed in this location (usually only done on the cluster master)| splunk.app_paths | **none** | no | no | no |
|httpinput| App to use and configure when setting up HEC based instances.| splunk.app_paths | **none** | no | no | no |

Search Head Clustering can be configured using the "shc" sub-object. Example:
```
        # Search Head Clustering
        shc:
            enable: false
            secret: <secret_key>
            replication_factor: 3
            replication_port: 4001
```
|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
|enable| Instructs the container to create a search head cluster | splunk.shc | false| no | yes | no |
|secret| A secret phrase to use for all SHC communication and binding. Please note, once set this can not be changed without rebuilding the cluster. | splunk.shc | **none** | no | yes | no |
|replication_factor| Consult docs.splunk.com for valid settings for your use case | splunk.shc | 3 | no | yes | no |
|replication_port| Default port for the SHC to communicate on | splunk.shc | 4001| no | yes | no |

Lastly, Index Clustering is configured with the `idxc` sub-object. Example:
```
        # Indexer Clustering
        idxc:
            secret: <secret_key>
            search_factor: 2
            replication_factor: 3
            replication_port: 9887
```
|Variable Name| Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
|---|---|:---:|:---:|:---:|:---:|:---:|
| secret | Secret used for transmission between the cluster master and indexers | splunk.idxc | **none** | no | no | yes |
| search_factor | Search factor to be used for search artifacts | splunk.idxc | 2 | no | no | yes |
| replication_factor | Bucket replication factor used between index peers | splunk.idxc | 3 | no | no | yes |
| replication_port | Bucket replication Port between index peers | splunk.idxc | 9887 | no | no | yes |


---

## Generating a default.yml file ##
The Docker Container contains a script for the generation of random keys, hec tokens, or passwords, and echoes them to stdout.  Run the following command to
generate a set of defaults that you can use in your environment

```
$ docker run --rm splunk/splunk-debian-9:latest create-defaults > test_scenarios/defaults/default.yml
```

you can also pre-seed the password in your default file:

```
$ docker run --rm -e "SPLUNK_PASSWORD=<password>" splunk/splunk-debian-9:latest create-defaults > <fullpath_to_images_repo>/test_scenarios/defaults/default.yml
```

## Starting Splunk Enterprise with a default.yml file ##
The following command is used to supply an advanced configuration to the container, specify a url location of the `default.yml` file, or volume mount in a default. To use the 
`default.yml` created on the previous section, use the following syntax:

```
$ docker run -d -p 8000:8000 -v <fullpath_to_images_repo>/test_scenarios/defaults:/tmp/defaults -e "SPLUNK_START_ARGS=--accept-license" -e "SPLUNK_PASSWORD=<password>" splunk/splunk-debian-9:latest
```


# Starting a Splunk Cluster

** Note: ** Splunk does not offer support for Docker or any orchestration
platforms like Kubernetes, Docker Swarm, Mesos, etc. Support covers only the
published Splunk Docker images. At this time, we strongly recommend that only
very experienced and advanced customers use Docker to run Splunk clusters*

While Splunk does not support orchestrators or the YAML templates required to
deploy and manage clusters and other advanced configurations, we provide several
examples of these different configurations in the "test_scenarios" folder. These are for prototyping purposes only.
One of the most common configurations of Splunk Enterprise is the C3 configuration
(see [Splunk Validated Architectures](https://www.splunk.com/pdfs/white-papers/splunk-validated-architectures.pdf) for more info).
This architecture contains a search head cluster, an index cluster, with a deployer and cluster master.

You can create a simple cluster with Docker Swarm using the following command:
```
 $> SPLUNK_COMPOSE=cluster_absolute_unit.yaml make sample-compose-up
```
Please note that the provisioning process will run for a few minutes after this command completes
while the Ansible plays run. Also, be warned that this configuration requires a lot of resources
so running this on your laptop may make it hot and slow. 

To view port mappings run: 
```
 $> docker ps 
```
After several minutes, you should be able to log into one of the search heads `sh#`
using the default username `admin` and the password you input at installation, or set through the Splunk UI. 

Once finished, you can remove the cluster by running:
```
 $> SPLUNK_COMPOSE=cluster_absolute_unit.yaml make sample-compose-down
```

The `cluster_absolute_unit.yaml` file located in the test_scenarios folder is a
Docker Compose file that can be used to mimic this type of deployment. 

```
version: "3.6"

networks:
  Splunknet:
    driver: bridge
    attachable: true
```

`version 3.6` is a reference to the Docker Compose version, while `networks` is a reference to the type of adapter that will be created for
the Splunk deployment to communicate across. For more information on the different types of network drivers, please consult your Docker installation manual.

In `cluster_absolute_unit.yaml`, all instances of Splunk Enterprise are created under one major service object.

```
services:
  sh1:
    networks:
      Splunknet:
        aliases:
          - sh1
    image: Splunk:latest
    hostname: sh1
    container_name: sh1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_INDEXER_URL=idx1,idx2,idx3,idx4
      - SPLUNK_SEARCH_HEAD_URL=sh2,sh3
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=sh1
      - SPLUNK_CLUSTER_MASTER_URL=cm1
      - SPLUNK_ROLE=Splunk_search_head_captain
      - SPLUNK_DEPLOYER_URL=dep1
      - SPLUNK_LICENSE_URI=<license uri> http://foo.com/splunk.lic
      - DEBUG=true
    ports:
      - 8000
    volumes:
      - ./defaults:/tmp/defaults
``` 
It's important to understand how Docker knows how to configure each major container. Below is the above template broken down into its simplest components:

```
services:
  <hostname of container>:
    networks:
      <name of network created in the first section>:
        aliases:
          - <a short name to reference this container>
    image: <what image to use for creating this container>
    hostname: <actual hostname of the container to use>
    container_name: <labeling the container>
    environment:
      - SPLUNK_START_ARGS=--accept-license <required in order to start container>
      - SPLUNK_INDEXER_URL=<list of each indexer's hostname>
      - SPLUNK_SEARCH_HEAD_URL= <list of each search head's hostnames>
      - SPLUNK_SEARCH_HEAD_CAPTAIN_URL=<hostname of which container to make the captain>
      - SPLUNK_CLUSTER_MASTER_URL=<hostname of the cluster master>
      - SPLUNK_ROLE=<what role to use for this container>
      - SPLUNK_DEPLOYER_URL=<hostname of the deployer>
      - SPLUNK_LICENSE_URI=<uri to your Splunk Enterprise license>
      - DEBUG=<true/false>
    ports:
      - 8000 <port to expose to the host>
    volumes:
      - ./defaults:/tmp/defaults <only used for volume mapping a default.yml>

```

Acceptable roles for SPLUNK_ROLE are as follows:
* splunk_standalone
* splunk_search_head
* splunk_indexer
* splunk_deployer
* splunk_license_master
* splunk_cluster_master
* splunk_heavy_forwarder

For more information about these roles, refer to [Splunk Splexicon](https://docs.splunk.com/splexicon).

After creating a Compose file, you can start an entire cluster with `docker-compose`:
```
docker-compose -f cluster_absolute_unit.yaml up -d
```

To support Splunk Enterprise's complex configurations, the Docker container utilizes Ansible which performs the required provisioning
commands. You can use the `docker log` command to follow these logs. 

`docker ps` will show a list of all the current running instances on this node. The cluster master gives the best indication of cluster health without needing to check every container.
```
$ docker ps
```
```
CONTAINER ID        IMAGE                    COMMAND                  CREATED             STATUS                             PORTS                                                                                      NAMES
69ed0d45a50b        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 8 seconds (health: starting)    4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32776->8000/tcp   idx2
760c4a8661dd        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 9 seconds (health: starting)    4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32775->8000/tcp   dep1
d6013cce3dfc        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 9 seconds (health: starting)    4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32773->8000/tcp   sh3
6b8da3c05e24        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 9 seconds (health: starting)    4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32774->8000/tcp   sh2
bbbe650dd544        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 9 seconds (health: starting)    4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32772->8000/tcp   cm1
46bc515059d5        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 9 seconds (health: starting)    4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32771->8000/tcp   sh1
b68d8215d00a        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 10 seconds (health: starting)   4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32770->8000/tcp   idx4
8b934acb20b5        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 10 seconds (health: starting)   4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32769->8000/tcp   idx1
9df560952f17        splunk-debian-9:latest   "/sbin/entrypoint.sh…"   11 seconds ago      Up 10 seconds (health: starting)   4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:32768->8000/tcp   idx3
```
Follow the stdout from the cluster master by running the following command:
```
docker logs -f <container-id>
```
In the above example, the container id is `bbbe650dd544`. So, the `docker logs` command would be run as follows:
```
docker logs -f bbbe650dd544
```
As Ansible runs, the results from each play can be seen on the screen as well as writen to an ansible.log file stored inside the container.
```
PLAY [localhost] ***************************************************************

TASK [Gathering Facts] *********************************************************
Wednesday 29 August 2018  09:27:06 +0000 (0:00:00.070)       0:00:00.070 ******
ok: [localhost]

TASK [include_role : Splunk_upgrade] *******************************************
Wednesday 29 August 2018  09:27:08 +0000 (0:00:02.430)       0:00:02.501 ******

TASK [include_role : {{ splunk_role }}] ****************************************
Wednesday 29 August 2018  09:27:09 +0000 (0:00:00.137)       0:00:02.638 ******

TASK [Splunk_common : Install Splunk] ******************************************
Wednesday 29 August 2018  09:27:09 +0000 (0:00:00.378)       0:00:03.016 ******
changed: [localhost]

TASK [Splunk_common : Install Splunk (Windows)] ********************************
Wednesday 29 August 2018  09:28:29 +0000 (0:01:20.307)       0:01:23.324 ******

TASK [Splunk_common : Generate user-seed.conf] *********************************
Wednesday 29 August 2018  09:28:29 +0000 (0:00:00.123)       0:01:23.447 ******
changed: [localhost] => (item=USERNAME)
changed: [localhost] => (item=PASSWORD)
```
Once Ansible has finished running, a summary screen will be displayed. 

```
PLAY RECAP *********************************************************************
localhost                  : ok=12   changed=6    unreachable=0    failed=1
`
Wednesday 29 August 2018  09:31:56 +0000 (0:00:01.435)       0:04:49.684 ******
===============================================================================
Splunk_common : Start Splunk ------------------------------------------ 105.37s
Splunk_common : Download Splunk license -------------------------------- 83.32s
Splunk_common : Install Splunk ----------------------------------------- 80.31s
Splunk_common : Apply Splunk license ------------------------------------ 6.31s
Splunk_common : Enable the Splunk-to-Splunk port ------------------------ 6.26s
Gathering Facts --------------------------------------------------------- 2.43s
Splunk_cluster_master : Set indexer discovery --------------------------- 1.44s
Splunk_common : include_tasks ------------------------------------------- 1.42s
Splunk_common : Generate user-seed.conf --------------------------------- 0.69s
Splunk_common : Set license location ------------------------------------ 0.59s
include_role : {{ Splunk_role }} ---------------------------------------- 0.37s
Splunk_common : include_tasks ------------------------------------------- 0.22s
Splunk_cluster_master : Get indexer count ------------------------------- 0.18s
Splunk_cluster_master : Get default replication factor ------------------ 0.18s
Splunk_common : Set as license slave ------------------------------------ 0.17s
include_role : Splunk_upgrade ------------------------------------------- 0.14s
Splunk_common : Install Splunk (Windows) -------------------------------- 0.12s
Splunk_cluster_master : Lower indexer search/replication factor --------- 0.10s
Stopping Splunkd...
Shutting down. Please wait, as this may take a few minutes.
..
Stopping Splunk helpers...

Done.
```
It's important to call out the `RECAP` line, as it's the biggest indicator if Splunk Enterprise was configured correctly. In this
example, there was a failure during the container creation. The offending play is:

```
TASK [Splunk_cluster_master : Set indexer discovery] ***************************
Wednesday 29 August 2018  09:31:54 +0000 (0:00:00.101)       0:04:48.249 ******
fatal: [localhost]: FAILED! => {"cache_control": "private", "changed": false, "connection": "Close", "content": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<response>\n  <messages>\n    <msg type=\"ERROR\">Unauthorized</msg>\n  </messages>\n</response>\n", "content_length": "130", "content_type": "text/xml; charset=UTF-8", "date": "Wed, 29 Aug 2018 09:31:56 GMT", "msg": "Status code was 401 and not [201, 409]: HTTP Error 401: Unauthorized", "redirected": false, "server": "Splunkd", "status": 401, "url": "https://127.0.0.1:8089/servicesNS/nobody/system/configs/conf-server", "vary": "Cookie, Authorization", "www_authenticate": "Basic realm=\"/Splunk\"", "x_content_type_options": "nosniff", "x_frame_options": "SAMEORIGIN"}
	to retry, use: --limit @/opt/ansible/ansible-retry/site.retry
```

In the above example, the `default.yml` file didn't contain a password, nor was an environment variable set. 

Please see the [troubleshooting](TROUBLESHOOTING.md) section for more common issues that can occur. There you will also find instructions for producing Splunk diagnostics for support such as `splunk diag`, as well as instructions for downloading the full Splunk `ansible.log` file.
