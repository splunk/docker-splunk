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
* [Using deployment servers](#using-deployment-servers)
* [Deploy distributed topology](#deploy-distributed-topology)
* [Enable SSL internal communication](#enable-ssl-internal-communication)
* [Build from source](#build-from-source)
    * [base-debian-9](#base-debian-9)
    * [splunk-debian-9](#splunk-debian-9)
    * [uf-debian-9](#uf-debian-9)

## Runtime configuration
Splunk's Docker image has several functions that can be configured. These options are specified by either supplying a `default.yml` file or by passing in environment variables. 

Passed in environment variables and/or default.yml are consumed by the inventory script in [splunk-ansible project](https://github.com/splunk/splunk-ansible).

Please refer to [Environment Variables List](https://splunk.github.io/splunk-ansible/ADVANCED.html#inventory-script)

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
| root_endpoint | Set root endpoint for SplunkWeb (for reverse proxy usage) | splunk | **none** | no | no | no |
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
          default_namespace: appboilerplate
          search_syntax_highlighting: dark
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
    index:
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

Some cache management options are also available. Options defined under the index stanza correspond to options in `indexes.conf` https://docs.splunk.com/Documentation/Splunk/latest/admin/Indexesconf. While options defined outside the index correspond to options in `server.conf` https://docs.splunk.com/Documentation/Splunk/latest/admin/Serverconf, note that currently only `[cachemanager]` stanza is supported. This is an example config that defines cache settings and retention policy:
```
smartstore:
  cachemanager:
    max_cache_size: 500
    max_concurrent_uploads: 7
  index:
    - indexName: custom_index
      remoteName: my_storage
      scheme: http
      remoteLocation: my_storage.net
      maxGlobalDataSizeMB: 500
      maxGlobalRawDataSizeMB: 200
      hotlist_recency_secs: 30
      hotlist_bloom_filter_recency_hours: 1
```

## Using deployment servers
Briefly, deployment servers can be used to manage otherwise unclustered/disjoint Splunk instances. A primary use-case would be to stand up a deployment server to manage app or configuration distribution to a fleet of 100 universal forwarders.

See the [full deployment server guide](advanced/DEPLOYMENT_SERVER.md) to understand how you can leverage this role in your topology.

## Deploy distributed topology
While running a standalone Splunk instance may be fine for testing and development, you may eventually want to scale out to enable better performance of running Splunk at scale. This image does support a fully-vetted distributed Splunk environment, by using environment variables that enable certain containers to assume certain roles, and to network everything together.

See the [instructions on standing up a distributed environment](advanced/DISTRIBUTED_TOPOLOGY.md) to understand how to get started.

## Enable SSL Internal Communication
For users looking to secure the network traffic from one Splunk instance to another Splunk instance (ex: forwarders to indexers), you can enable forwarding and receiving to use SSL certificates. 

If you wish to enable SSL on one tier of your Splunk topology, it's very likely all instances will need it. To achieve this, we recommend you generate your server and CA certificates and add them to the `default.yml` which gets shared across all Splunk docker containers. Use this example `default.yml` snippet for the configuration of Splunk TCP with SSL.  
```
splunk:
  ...
  s2s:
    ca: /mnt/certs/ca.pem
    cert: /mnt/certs/cert.pem
    enable: true
    password: abcd1234
    port: 9997
    ssl: true
  ...
```

For more instructions on how to bring your own certificates, please see: https://docs.splunk.com/Documentation/Splunk/latest/Security/ConfigureSplunkforwardingtousesignedcertificates

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
    $ make splunk-redhat-8
    $ make uf-redhat-8
    ```

Additionally, there are multiple images and layers that are produced by the previous commands: `base-redhat-8`, `splunk-redhat-8`, and `uf-redhat-8`.

#### base-redhat-8
The directory `base-redhat-8` contains a Dockerfile to create a base image on top of which all the other images are built. In order to minimize image size and provide a stable foundation for other images to build on, we elected to use `registry.access.redhat.com/ubi8/ubi-minimal:8.0` (90MB) for our base image. In the future, we plan to add support for additional operating systems.
```
$ make base-redhat-8
```

**WARNING:** Modifications made to the "base" image can result in Splunk being unable to start or run correctly.

#### splunk-redhat-8
The directory `splunk/common-files` contains a Dockerfile that extends the base image by installing Splunk and adding tools for provisioning. Advanced Splunk provisioning capabilities are provided through the utilization of an entrypoint script and playbooks published separately via the [splunk-ansible project](https://github.com/splunk/splunk-ansible).
```
$ make splunk-redhat-8
```

#### uf-redhat-8
The directory `uf/common-files` contains a Dockerfile that extends the base image by installing Splunk Universal Forwarder and adding tools for provisioning. This image is similar to the Splunk Enterprise image (`splunk-redhat-8`), except the more lightweight Splunk Universal Forwarder package is installed instead.
```
$ make uf-redhat-8
```
