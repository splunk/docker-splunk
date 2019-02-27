## Advanced

Let's dive into the nitty-gritty on how to tweak the setup of your containerized Splunk deployment. This section goes over in detail various features and functionality that a traditional Splunk Enterprise solution is capable of.

## Navigation

* [Runtime configuration](#runtime-configuration)
    * [Valid Splunk env vars](#valid-splunk-env-vars)
    * [Valid UF env vars](#valid-uf-env-vars)
    * [Using default.yml](#using-default.yml)
        * [Generation](#generation)
        * [Usage](#usage)
        * [Spec](#spec)
* [Entrypoint Functions](#entrypoint-functions)
* [Install apps](#install-apps)
* [Apply Splunk license](#apply-splunk-license)
* [Create custom configs](#create-custom-configs)
* [Enable SmartStore](#enable-smartstore)
* [Deploy distributed topology](#deploy-distributed-topology)
* [Build from source](#build-from-source)
    * [base-debian-9](#base-debian-9)
    * [splunk-debian-9](#splunk-debian-9)
    * [uf-debian-9](#uf-debian-9)

## Runtime configuration
Splunk's Docker image has several functions that can be configured. These options are specified by either supplying a `default.yml` file or
by passing in environment variables. Below is a list of environment variables that may/must be used when starting the container.

#### Valid Splunk env vars
| Environment Variable Name | Description | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- |
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
| SPLUNK_HEAVY_FORWARDER_URL | List of all Splunk Enterprise heavy forwarder hosts (network alias) separated by comma | no | no | no |
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
| STEPDOWN_ANSIBLE_USER | Removes Ansible user from the sudo group when set to true. This means that no other users than root will have root access. | no | no | no |
| SPLUNK_HOME_OWNERSHIP_ENFORCEMENT | Recursively enforces ${SPLUNK_HOME} to be owned by the user "splunk". Default value is true. | no | no | no |
| HIDE_PASSWORD | Set to true to hide all Ansible task logs with Splunk password in them in order to secure our output to stdout. | no | no | no |
| JAVA_VERSION | Supply "oracle:8", "openjdk:8", or "openjdk:11" to install a respective Java distribution. | no | no | no |

* Password must be set either in default.yml or as the environment variable `SPLUNK_PASSWORD`

#### Valid UF env vars
The `splunk/universalforwarder` image accepts the majority* environment variables as the `splunk/splunk` image above. However, there are some additional ones that are specific to the Universal Forwarder.

* **Note:** Specifically for the `splunk/universalforwarder` image, the environment variable `SPLUNK_ROLE` will by default be set to `splunk_universal_forwarder`. This image cannot accept any other role, and should not be changed (unlike its `splunk/splunk` image counterpart).

| Environment Variable Name | Description | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- |
| SPLUNK_DEPLOYMENT_SERVER | One Splunk host (network alias) that we use as a [deployment server](http://docs.splunk.com/Documentation/Splunk/latest/Updating/Configuredeploymentclients) | no | no | no |
| SPLUNK_ADD | List of items to add to monitoring separated by comma. Example, SPLUNK_ADD=udp 1514,monitor /var/log/\*. This will monitor udp 1514 port and /var/log/\* files. | no | no | no |
| SPLUNK_BEFORE_START_CMD | List of commands to run before Splunk starts separated by comma. Ansible will run “{{splunk.exec}} {{item}}”. | no | no | no |
| SPLUNK_CMD | List of commands to run after Splunk starts separated by comma. Ansible will run “{{splunk.exec}} {{item}}”. | no | no | no |
| DOCKER_MONITORING | True or False. This will install Docker monitoring apps. | no | no | no |

#### Using default.yml
The purpose of the `default.yml` is to define a standard set of variables that controls how Splunk gets set up. This is particularly important when deploying clustered Splunk topologies, as there are frequent variables that you need to be consistent across all members of the cluster (ex. keys, passwords, secrets).

##### Generation
The image contains a script to enable dynamic generation of this file automatically. Run the following command to generate a `default.yml`:
```
$ docker run --rm -it splunk/splunk:latest create-defaults > default.yml
```

You can also pre-seed some settings based on environment variables during this `default.yml` generation process. For instance, you can define `SPLUNK_PASSWORD` as so:
```
$ docker run --rm -it -e SPLUNK_PASSWORD=<password> splunk/splunk:latest create-defaults > default.yml
```
##### Usage
When starting the docker container, this `default.yml` can be mounted in `/tmp/defaults/default.yml` or it can be fetched dynamically with `SPLUNK_DEFAULTS_URL`, and the provisioning done by Ansible will read in and honor these settings. Note that environment variables specified at runtime will take precendence over things defined in `default.yml`.
```
# Volume-mounting option
$ docker run -d -p 8000:8000 -v default.yml:/tmp/defaults/default.yml -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD=<password> splunk/splunk:latest

# URL option
$ docker run -d -p 8000:8000 -v -e SPLUNK_DEFAULTS_URL=http://company.net/path/to/default.yml -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD=<password> splunk/splunk:latest
```

##### Spec
Root items influence the behavior of everything in the container; they have global scope inside the container.
Example:
```
---
retry_num: 100
```

| Variable Name | Description | Parent Object | Default Value | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- | --- | --- |
| retry_num | Default number of loop attempts to connect containers | none | 100 | yes | yes | yes |

The major object "splunk" in the YAML file will contain variables that influence how Splunk operates. Example:
```
splunk:
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
  # The hec_token here is used for INGESTION only. By that I mean receiving Splunk events.
  # Setting up your environment to forward events out of the cluster is another matter entirely
  hec_token: <default_hec_token>
  # This option here is to enable the SmartStore feature
  smartstore: null
```

| Variable Name | Description | Parent Object | Default Value | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- | --- | --- |
| opt | Parent directory where Splunk is running | splunk | /opt | yes | yes | yes |
| home | Location of the Splunk Installation | splunk | /opt/splunk | yes | yes | yes |
| user | Operating System User to Run Splunk Enterprise As | splunk | splunk | yes | yes | yes |
| group | Operating System Group to Run Splunk Enterprise As | splunk | splunk | yes | yes | yes |
| exec | Path to the Splunk Binary | splunk | /opt/splunk/bin/splunk | yes | yes | yes |
| pid | Location to the Running PID File | splunk | /opt/splunk/var/run/splunk/splunkd.pid | yes | yes | yes
| password | Password for the admin account | splunk | **none** | yes | yes | yes |
| svc_port | Default Admin Port | splunk | 8089 | yes | yes | yes |
| s2s_port | Default Forwarding Port | splunk | 9997 | yes | yes | yes |
| http_port | Default SplunkWeb Port | splunk | 8000 | yes | yes | yes |
| hec_port | Default HEC Input Port | splunk | 8088 | no | no | no |
| hec_disabled | Enable / Disable HEC | splunk | 0 | no | no | no |
| hec_enableSSL | Force HEC to use encryption | splunk | 1 | no | no | no |
| hec_token | Token to enable for HEC inputs | splunk | **none** | no | no | no |
| smartstore | Configuration params for [SmartStore](https://docs.splunk.com/Documentation/Splunk/latest/Indexer/AboutSmartStore) bootstrapping | splunk | null | no | no | no |

The app_paths section is located as part of the "splunk" parent object. The settings located in this section will directly influence how apps are installed inside the container. Example:
```
  app_paths:
    default: /opt/splunk/etc/apps
    shc: /opt/splunk/etc/shcluster/apps
    idxc: /opt/splunk/etc/master-apps
    httpinput: /opt/splunk/etc/apps/splunk_httpinput
```

| Variable Name | Description | Parent Object | Default Value | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- | --- | --- |
| default | Normal apps for standalone instances will be installed in this location | splunk.app_paths | **none** | no | no | no |
| shc | Apps for search head cluster instances will be installed in this location (usually only done on the deployer)| splunk.app_paths | **none** | no | no | no |
| idxc | Apps for index cluster instances will be installed in this location (usually only done on the cluster master)| splunk.app_paths | **none** | no | no | no |
| httpinput | App to use and configure when setting up HEC based instances.| splunk.app_paths | **none** | no | no | no |

Search Head Clustering can be configured using the "shc" sub-object. Example:
```
  shc:
    enable: false
    secret: <secret_key>
    replication_factor: 3
    replication_port: 9887
```
| Variable Name | Description | Parent Object | Default Value | Required for Standalone | Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- | --- | --- |
| enable | Instructs the container to create a search head cluster | splunk.shc | false | no | yes | no |
| secret | A secret phrase to use for all SHC communication and binding. Please note, once set this can not be changed without rebuilding the cluster. | splunk.shc | **none** | no | yes | no |
| replication_factor | Consult docs.splunk.com for valid settings for your use case | splunk.shc | 3 | no | yes | no |
| replication_port | Default port for the SHC to communicate on | splunk.shc | 9887 | no | yes | no |

Lastly, Index Clustering is configured with the `idxc` sub-object. Example:
```
  idxc:
    secret: <secret_key>
    search_factor: 2
    replication_factor: 3
    replication_port: 9887
```
| Variable Name | Description | Parent Object | Default Value | Required for Standalone| Required for Search Head Clustering | Required for Index Clustering |
| --- | --- | --- | --- | --- | --- | --- |
| secret | Secret used for transmission between the cluster master and indexers | splunk.idxc | **none** | no | no | yes |
| search_factor | Search factor to be used for search artifacts | splunk.idxc | 2 | no | no | yes |
| replication_factor | Bucket replication factor used between index peers | splunk.idxc | 3 | no | no | yes |
| replication_port | Bucket replication Port between index peers | splunk.idxc | 9887 | no | no | yes |

## Install apps 
Briefly, apps can be installed by using the `SPLUNK_APPS_URL` environment variable when creating the Splunk container:
```
$ docker run -it --name splunk -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD=<password> -e SPLUNK_APPS_URL=http://company.com/path/to/app.tgz splunk/splunk:latest
```

See the [full app installation walkthrough](advanced/APP_INSTALL.md) to understand how to specify multiple apps and how to apply it in a distributed environment.

## Apply Splunk license
Briefly, licenses can be added with the `SPLUNK_LICENSE_URI` environment variable when creating the Splunk container:
```
$ docker run -it --name splunk -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_PASSWORD=<password> -e SPLUNK_LICENSE_URI=http://company.com/path/to/splunk.lic splunk/splunk:latest
```

See the [full license installation guide](advanced/LICENSE_INSTALL.md) to understand how to specify multiple licenses and how to use a central, containerized license manager.

## Create custom configs
When Splunk boots, it registers all the config files in various locations on the filesystem under `${SPLUNK_HOME}`. These are settings that control how Splunk operates. For more information, please see the [documentation from Splunk](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Aboutconfigurationfiles).

Using the Docker image, it is also possible for users to create their own config files, following the same INI-style that drives Splunk. This is a power-user/admin-level feature, as invalid config files may break or prevent start-up of your Splunk installation!

User-specified configuration files are only possible through the use of a `default.yml`. Please set a `conf` key under the greater `splunk` key using the format shown below.
```
---
splunk:
  conf:
    user-prefs:
      directory: /opt/splunkforwarder/etc/users/admin/user-prefs/local
      content:
        general:
          default_namespace : appboilerplate
          search_syntax_highlighting : dark
  ...
```

This will generate a file owned by the correct Splunk user and group, named `user-prefs.conf` and located within the `directory` (in this case, `/opt/splunkforwarder/etc/users/admin/user-prefs/local`). Because it follows INI-format, the contents of the final file will resemble the following:
```
[general]
search_syntax_highlighting = dark
default_namespace = appboilerplate
```

For multiple custom configuration files, please add more entries under the `conf` key of the `default.yml`.

**CAUTION:** Using this method of configuration file generation may not create a configuration file the way Splunk expects. Verify the generated configuration file to avoid errors. Use at your own discretion.

## Enable SmartStore
SmartStore utilizes S3-compliant object storage in order to store indexed data. This is a capability only available if you're using an indexer cluster (cluster_master + indexers). For more information, please see the [blog post](https://www.splunk.com/blog/2018/10/11/splunk-smartstore-cut-the-cord-by-decoupling-compute-and-storage.html) as well as [technical overview](https://docs.splunk.com/Documentation/Splunk/latest/Indexer/AboutSmartStore).

This docker image is capable of support SmartStore, as long as you bring-your-own backend storage provider. Due to the complexity of this option, this is only enabled if you specify all the parameters in your `default.yml` file. 

Here's an overview of what this looks like if you want to persist *all* your indexes (default) with a SmartStore backend:
```
---
splunk:
  smartstore:
    - indexName: default
      remoteName: remote_store
      scheme: s3
      remoteLocation: <bucket-name>
      s3:
        access_key: <access_key>
        secret_key: <secret_key>
        endpoint: http://s3-us-west-2.amazonaws.com
  ...
```

## Deploy distributed topology
While running a standalone Splunk instance may be fine for testing and development, you may eventually want to scale out to enable better performance of running Splunk at scale. This image does support a fully-vetted distributed Splunk environment, by using environment variables that enable certain containers to assume certain roles, and to network everything together.

See the [instructions on standing up a distributed environment](advanced/DISTRIBUTED_TOPOLOGY.md) to understand how to get started.

## Build from source
While we don't support or recommend you building your own images from source, it is entirely possible. This can be useful if you want to incorporate very experimental features, test new features, and if you have your own registry for persistent images.

To build images directly from this repository, there is a supplied `Makefile` in the root of the project with commands and variables to control the build:
1. Fork the [docker-splunk GitHub repository](https://github.com/splunk/docker-splunk/issues)
2. Clone your fork using git and create a branch off develop
    ```
    $ git clone git@github.com:YOUR_GITHUB_USERNAME/docker-splunk.git
    $ cd docker-splunk
    ```
3. Run all the tests to verify your environment
    ```
    $ make splunk-debian-9
    $ make uf-debian-9
    ```

Additionally, there are multiple images and layers that are produced by the previous commands: `base-debian-9`, `splunk-debian-9`, and `uf-debian-9`.

#### base-debian-9
The directory `base/debian-9` contains a Dockerfile to create a base image on top of which all the other images are built. In order to minimize image size and provide a stable foundation for other images to build on, we elected to use `debian:stretch-slim` (55MB) for our base image. In the future, we plan to add support for additional operating systems.
```
$ make base-debian-9
```

**WARNING:** Modifications made to the "base" image can result in Splunk being unable to start or run correctly.

#### splunk-debian-9
The directory `splunk/debian-9` contains a Dockerfile that extends the base image by installing Splunk and adding tools for provisioning. Advanced Splunk provisioning capabilities are provided through the utilization of an entrypoint script and playbooks published separately via the [splunk-ansible project](https://github.com/splunk/splunk-ansible).
```
$ make splunk-debian-9
```

#### uf-debian-9
The directory `uf/debian-9` contains a Dockerfile that extends the base image by installing Splunk Universal Forwarder and adding tools for provisioning. This image is similar to the Splunk Enterprise image (`splunk-debian-9`), except the more lightweight Splunk Universal Forwarder package is installed instead.
```
$ make uf-debian-9
```
