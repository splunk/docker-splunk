## Navigation

* [Install](#install)
* [Configure](#configure)
* [Run](#run)
    * [Splunk Enterprise](#splunk-enterprise)
    * [Splunk Universal Forwarder](#splunk-universal-forwarder)
* [Summary](#summary)

----

## Install

This codebase produces a Docker image, which is currently the only supported container runtime engine for this project. In order to run the Splunk Docker image, you will need the following prerequisites and dependencies installed on each node you plan on deploying Splunk:
1. Linux-based operating system (Debian, CentOS, etc.)
2. Kernel version > 4.0
3. Docker engine
    * Docker Enterprise Engine 17.06.2 or later
    * Docker Community Engine 17.06.2 or later
4. `overlay2` Docker daemon storage driver
5. [Splunk hardware and capacity recommendations](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements)

If you intend for the containerized Splunk Enterprise deployment to be supported by your Enterprise Support Agreement, you must verify you meet all of the above "supported" requirements. Failure to do so will render your deployment in an "unsupported" state.

For more details, please see the official [supported architectures and platforms for containerized Splunk environments](https://docs.splunk.com/Documentation/Splunk/latest/Installation/Systemrequirements#Containerized_computing_platforms). 

## Configure
Before we can run the containers, we should pull it down from DockerHub. Run the following commands to pull the images into your local environment:
```
$ docker pull splunk/splunk:latest
$ docker pull splunk/universalforwarder:latest
```

## Run
Before we stand up any containers, let's first create a network to enable networking between each of the services.
```
$ docker network create --driver bridge --attachable skynet
```

#### Splunk Enterprise
Use the following command to start a single standalone instance of Splunk Enterprise:
```
$ docker run --network skynet --name so1 --hostname so1 -p 8000:8000 -e "SPLUNK_PASSWORD=<password>" -e "SPLUNK_START_ARGS=--accept-license" -it splunk/splunk:latest
```

Let's break down what this command does:
1. Start a Docker container using the `splunk/splunk:latest` image
2. Launch the container in the formerly-created bridge network `skynet`
3. Name the container + hostname as `so1`
4. Expose a port mapping from the host's `8000` to the container's `8000`
5. Specify a custom `SPLUNK_PASSWORD` - be sure to replace `<password>` with any string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile)
6. Accept the license agreement with `SPLUNK_START_ARGS=--accept-license` - this must be explicitly accepted on every container, otherwise Splunk will not start

After the container starts up successfully, you should be able to access SplunkWeb at http://localhost:8000 with `admin:<password>`.

#### Splunk Universal Forwarder
Use the following command to start a single standalone instance of Splunk Enterprise:
```
$ docker run --network skynet --name uf1 --hostname uf1 -e "SPLUNK_PASSWORD=<password>" -e "SPLUNK_START_ARGS=--accept-license" -e "SPLUNK_STANDALONE_URL=so1" -it splunk/universalforwarder:latest
```

Now let's run the same analysis on what we just did:
1. Start a Docker container using the `splunk/universalforwarder:latest` image
2. Launch the container in the formerly-created bridge network `skynet`
3. Name the container + hostname as `uf1`
4. Specify a custom `SPLUNK_PASSWORD` - be sure to replace `<password>` with any string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile)
5. Accept the license agreement with `SPLUNK_START_ARGS=--accept-license` - this must be explicitly accepted on every container, otherwise Splunk will not start
6. Direct it to the standalone created earlier so the forwarder will automatically send its logs to `so1`

**NOTE:** The Splunk Universal Forwarder product does not have a web interface - if you require access to the Splunk installation in this particular container, please refer to the [REST API](https://docs.splunk.com/Documentation/Splunk/latest/RESTREF/RESTprolog) or use `docker exec` to access the [Splunk CLI](https://docs.splunk.com/Documentation/Splunk/latest/Admin/CLIadmincommands).

## Summary
You've successfully used `docker-splunk`! 

If everything went smoothly, you can login to the standalone Splunk with your browser pointed at `http://localhost:8000`, then run a search to confirms the logs are available. For example, a `search index=_internal` should return all the internal Splunk logs for both `host=so1` and `host=uf1`.

Ready for more? Now that your feet are wet, go learn more about the [design and architecture](ARCHITECTURE.md) or run through more [complex scenarios](ADVANCED.md).
