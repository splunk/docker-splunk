## Installing a Splunk Enterprise License
The Splunk Docker image supports the ability to bring your own Enterprise license. By default, the image includes the ability to use up to the trial license. Please see the documentation for more information on what [additional features and capabilities are unlocked with a full Enterprise license](https://docs.splunk.com/Documentation/Splunk/latest/Admin/HowSplunklicensingworks)

There are primarily two different ways to apply a license when starting your container: either through a file/directory volume-mounted inside the container, or through an external URL for dynamic downloads. The environment variable `SPLUNK_LICENSE_URI` supports both of these methods.


## Navigation

* [Path to file](#path-to-file)
* [Download via URL](#download-via-url)
* [Free license](#splunk-free-license)
* [Using a license master](#using-a-license-master)
* [Using a remote instance](#using-a-remote-instance)

## Path to file
We recommend using [Docker Secrets](https://docs.docker.com/engine/swarm/secrets) to manage your license. However, in a development environment, you can also specify a volume-mounted path to a file.

If you plan on using secrets storage, the initial step must be to create that secret. In the case of using Docker, you can run:
```
$ docker secret create splunk_license path/to/splunk.lic
```

Please refer to these separate docker-compose.yml files for how to use secrets or direct volume mounts:
<details><summary>docker-compose.yml - with secret</summary><p>

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_LICENSE_URI=/run/secrets/splunk_license
      - SPLUNK_PASSWORD
    ports:
      - 8000
    secrets:
      - splunk_license
secrets:
    splunk_license:
        external: true
```
</p></details>

<details><summary>docker-compose.yml - with volume mount</summary><p>

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_LICENSE_URI=/tmp/splunk.lic
      - SPLUNK_PASSWORD
    ports:
      - 8000
    volumes:
      - ./splunk.lic:/tmp/splunk.lic
```
</p></details>

You should be able to bring up your deployment with the Splunk license automatically applied with the following command:
```
$ SPLUNK_PASSWORD=<password> docker stack deploy --compose-file=docker-compose.yml splunk_deployment
```

## Download via URL
If you plan on hosting your license on a reachable file server, you can dynamically fetch and download your license from the container. This can be an easy way use a license without pre-seeding your container's environment runtime with various secrets/files.

Please refer to the following compose file for how to use a URL:
<details><summary>docker-compose.yml - with URL</summary><p>

```
version: "3.6"

services:
  so1:
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    hostname: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_LICENSE_URI=http://webserver/path/to/splunk.lic
      - SPLUNK_PASSWORD
    ports:
      - 8000
```
</p></details>

You should be able to bring up your deployment with the Splunk license automatically applied with the following command:
```
$ SPLUNK_PASSWORD=<password> docker stack deploy --compose-file=docker-compose.yml splunk_deployment
```

## Splunk Free license
Not to be confused with an actual free Splunk enterprise license, but [Splunk Free](https://docs.splunk.com/Documentation/Splunk/latest/Admin/MoreaboutSplunkFree) is a product offering that enables the power of Splunk with a never-expiring but ingest-limited license. By default, when you create a Splunk environment using this Docker container, it will enable a Splunk Trial license which is good for 30 days from the start of your instance. With Splunk Free, you can create a full developer environment of Splunk for any personal, sustained usage.

To bring up a single instance using Splunk Free, you can run the following command:
```
$ docker run --name so1 --hostname so1 -p 8000:8000 -e SPLUNK_PASSWORD=<password> -e SPLUNK_START_ARGS=--accept-license -e SPLUNK_LICENSE_URI=Free -it splunk/splunk:latest
```

## Using a license master
When starting up a distributed Splunk deployment, it may be inefficient for each Splunk instance to apply/fetch the same license. Luckily, there is a dedicated Splunk role for this - `splunk_license_master`. For more information on what this role is, please refer to Splunk documentation on [license masters](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Configurealicensemaster).

Please refer to the following compose file for how to bring up a license master:
<details><summary>docker-compose.yml - license master</summary><p>

```
version: "3.6"

networks:
  splunknet:
    driver: bridge
    attachable: true

services:
  lm1:
    networks:
      splunknet:
        aliases:
          - lm1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: lm1
    container_name: lm1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_STANDALONE_URL=so1
      - SPLUNK_LICENSE_MASTER_URL=lm1
      - SPLUNK_ROLE=splunk_license_master
      - SPLUNK_LICENSE_URI=http://webserver/path/to/splunk.lic
      - SPLUNK_PASSWORD

  so1:
    networks:
      splunknet:
        aliases:
          - so1
    image: ${SPLUNK_IMAGE:-splunk/splunk:latest}
    command: start
    hostname: so1
    container_name: so1
    environment:
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_STANDALONE_URL=so1
      - SPLUNK_LICENSE_MASTER_URL=lm1
      - SPLUNK_ROLE=splunk_standalone
      - SPLUNK_PASSWORD
    ports:
      - 8000
```
</p></details>

Note that in the above, only the license master container `lm1` needs to download and apply the license. When the standalone `so1` container comes up, it will detect (based off the environment variable `SPLUNK_LICENSE_MASTER_URL`) that there is a central license master, and consequently add itself as a license slave to that host.

## Using a remote instance
Alternatively, you may elect to create your Splunk environment all within containers but host the license master externally such that it can be used by multiple teams or organizations. These images support this type of configuration, through the following example:
```yaml
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
      - SPLUNK_STANDALONE_URL=so1
      - SPLUNK_LICENSE_MASTER_URL=http://central-license-master.internal.com:8088
      - SPLUNK_ROLE=splunk_standalone
      - SPLUNK_PASSWORD
    ports:
      - 8000
```

Note that it's possible to use a different protocol and port when supplying the license master URL. If scheme and port are not provided, the playbooks fall back to using `https` and the `8089` Splunk Enterprise management port.
