## Navigation

* [Requirements](#requirements)
* [Install](#install)
* [Deploy](#deploy)
    * [Standalone deployment](#standalone-deployment)
    * [Distributed deployment](#distributed-deployment)
* [See also](#see-also)

## Requirements
In order to run this Docker image, you must meet the official [System requirements](SUPPORT.md#system-requirements). Failure to do so will render your deployment in an unsupported state. See [Support violation](SUPPORT.md##support-violation) for details.

## Install
Run the following commands to pull the latest images down from Docker Hub and into your local environment:
```
$ docker pull splunk/splunk:latest
$ docker pull splunk/universalforwarder:latest
```

## Deploy

This section explains how to start basic standalone and distributed deployments. See the [Examples](EXAMPLES.md) page for instructions on creating additional types of deployments.

### Standalone deployment

Start a single containerized instance of Splunk Enterprise with the command below, replacing `<password>` with a password string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile).

```bash
$ docker run -p 8000:8000 -e "SPLUNK_PASSWORD=<password>" \
             -e "SPLUNK_START_ARGS=--accept-license" \
             -it splunk/splunk:latest
```

This command does the following:
1. Starts a Docker container using the `splunk/splunk:latest` image.
1. Exposes a port mapping from the host's `8000` port to the container's `8000` port
1. Specifies a custom `SPLUNK_PASSWORD`.
1. Accepts the license agreement with `SPLUNK_START_ARGS=--accept-license`. This agreement must be explicitly accepted on every container, or Splunk Enterprise doesn't start.

**You successfully created a standalone deployment with `docker-splunk`!**

After the container starts up, you can access Splunk Web at <http://localhost:8000> with `admin:<password>`.

### Distributed deployment

Start a Splunk Universal Forwarder running in a container to stream logs to a Splunk Enterprise standalone instance, also running in a container.

First, create a [network](https://docs.docker.com/engine/reference/commandline/network_create/) to enable communication between each of the services.

```
$ docker network create --driver bridge --attachable skynet
```

#### Splunk Enterprise
Start a single, standalone instance of Splunk Enterprise in the network created above, replacing `<password>` with a password string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile).
```bash
$ docker run --network skynet --name so1 --hostname so1 -p 8000:8000 \
              -e "SPLUNK_PASSWORD=<password>" \
              -e "SPLUNK_START_ARGS=--accept-license" \
              -it splunk/splunk:latest
```

This command does the following:
1. Starts a Docker container using the `splunk/splunk:latest` image.
1. Launches the container in the formerly-created bridge network `skynet`.
1. Names the container and the host as `so1`.
1. Exposes a port mapping from the host's `8000` port to the container's `8000` port
1. Specifies a custom `SPLUNK_PASSWORD`.
1. Accepts the license agreement with `SPLUNK_START_ARGS=--accept-license`. This agreement must be explicitly accepted on every container, or Splunk Enterprise doesn't start.

After the container starts up successfully, you can access Splunk Web at <http://localhost:8000> with `admin:<password>`.

#### Splunk Universal Forwarder
Start a single, standalone instance of Splunk Universal Forwarder in the network created above, replacing `<password>` with a password string that conforms to the [Splunk Enterprise password requirements](https://docs.splunk.com/Documentation/Splunk/latest/Security/Configurepasswordsinspecfile).
```bash
$ docker run --network skynet --name uf1 --hostname uf1 \
              -e "SPLUNK_PASSWORD=<password>" \
              -e "SPLUNK_START_ARGS=--accept-license" \
              -e "SPLUNK_STANDALONE_URL=so1" \
              -it splunk/universalforwarder:latest
```

This command does the following:
1. Starts a Docker container using the `splunk/universalforwarder:latest` image.
1. Launches the container in the formerly-created bridge network `skynet`.
1. Names the container and the host as `uf1`.
1. Specifies a custom `SPLUNK_PASSWORD`.
1. Accepts the license agreement with `SPLUNK_START_ARGS=--accept-license`. This agreement must be explicitly accepted on every container, otherwise Splunk Enterprise doesn't start.
1. Connects it to the standalone instance created earlier to automatically send logs to `so1`.

**NOTE:** The Splunk Universal Forwarder does not have a web interface. If you require access to the Splunk installation in this particular container, refer to the [REST API](https://docs.splunk.com/Documentation/Splunk/latest/RESTREF/RESTprolog) documentation or use `docker exec` to access the [Splunk CLI](https://docs.splunk.com/Documentation/Splunk/latest/Admin/CLIadmincommands).

**You successfully created a distributed deployment with `docker-splunk`!**

If everything went smoothly, you can log in to your Splunk Enterprise instance at <http://localhost:8000>, and then run a search to confirm the logs are available. For example, a query such as `index=_internal` should return all the internal Splunk logs for both `host=so1` and `host=uf1`.

## See also

* [More examples of standalone and distributed deployments](EXAMPLES.md)
* [Design and architecture of docker-splunk](ARCHITECTURE.md)
* [Adding advanced complexity to your containerized Splunk deployments](ADVANCED.md)
