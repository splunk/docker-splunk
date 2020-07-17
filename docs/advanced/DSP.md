## Data Stream Processor
[Splunk Data Stream Processor](https://www.splunk.com/en_us/software/stream-processing.html) is a separate service that can be used to collect and facilitate real-time stream processing. For more information, visit the [Splunk Data Stream Processor documentation](https://docs.splunk.com/Documentation/DSP).

The Splunk Docker image supports native integration with DSP through forwarders. Both universal and heavy forwarders can be automatically provisioned to send traffic to DSP, wherein custom pipelines can be configured to redirect and reformat the data as desired.

## Navigation

* [Forwarding traffic](#forwarding-traffic)
  * [User-generated certificates](#user-generated-certificates)
  * [Auto-generated certificates](#auto-generated-certificates)
* [Defining pipelines ](#defining-pipelines)

## Forwarding Traffic
Splunk DSP pipelines can be used to [process forwarder data](https://docs.splunk.com/Documentation/DSP/1.1.0/User/SenddataUF), either from a `splunk_universal_forwarder` or a `splunk_heavy_forwarder` role.

You will need [`scloud`](https://github.com/splunk/splunk-cloud-sdk-go) before proceeding.

### User-generated certificates
In order to get data into DSP, you must generate a client certificate and register it to the DSP forwarder service. Instructions for this can be found [here](https://docs.splunk.com/Documentation/DSP/1.1.0/Data/Forwarder), or as follows:
```bash
$ openssl genrsa -out my_forwarder.key 2048
$ openssl req -new -key "my_forwarder.key" -out "my_forwarder.csr" -subj "/C=US/ST=CA/O=my_organization/CN=my_forwarder/emailAddress=email@example.com"
$ openssl x509 -req -days 730 -in "my_forwarder.csr" -signkey "my_forwarder.key" -out "my_forwarder.pem" -sha256
$ cat my_forwarder.pem my_forwarder.key > my_forwarder-keys.pem
$ scloud forwarders add-certificate --pem "$(<my_forwarder.pem)" 
```

Once you have the resulting `my_forwarder-keys.pem`, this can be mounted into the container and used immediately. Refer to the following `docker-compose.yml` example below:
```yaml
version: "3.6"

services:
  hf1:
    image: splunk/splunk:8.0.5
    hostname: hf1
    environment:
      - SPLUNK_ROLE=splunk_heavy_forwarder
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_PASSWORD=helloworld
      - SPLUNK_DSP_ENABLE=true
      - SPLUNK_DSP_CERT=/opt/splunk/etc/auth/mycerts/my_forwarder-keys.pem
      - SPLUNK_DSP_SERVER=dsp-master-node.hostname:30001
    ports:
      - 8000
      - 8089
    volumes:
      - ./my_forwarder-keys.pem:/opt/splunk/etc/auth/mycerts/my_forwarder-keys.pem
```

Alternatively, this can also be done using the `default.yml` as so:
```yaml
---
splunk:
  dsp:
    enable: True
    server: dsp-master-node.hostname:30001
    cert: /opt/splunk/etc/auth/mycerts/my_forwarder-keys.pem
  ...
```

### Auto-generated Certificates
If you're just getting your feet wet with DSP and these Docker images, it can be helpful to rely on the Docker image to generate the certificates for you. Using `SPLUNK_DSP_CERT=auto` or `splunk.dsp.cert: auto` will let the container to create the certificate and print it out through the container's logs for you to register yourself:
```bash
$ scloud forwarders add-certificate --pem "<copied from cert printed to container stdout>" 
```

## Defining Pipelines
In addition to native support for sending data, the Docker image is also capable of configuring the pipeline in DSP which can be useful in declaratively defining the full end-to-end parsing and ingest 

You will need [`scloud`](https://github.com/splunk/splunk-cloud-sdk-go) before proceeding. In addition, you'll need an `scloud.toml` and `.scloud_context` with permissions enabled to read/write to your DSP installation.

Pipeline specifications are defined using [SPL2](https://docs.splunk.com/Documentation/DSP/1.1.0/User/SPL2). Refer to the following `docker-compose.yml` example below:
```yaml
version: "3.6"

services:
  hf1:
    image: splunk/splunk:8.0.5
    hostname: hf1
    environment:
      - SPLUNK_ROLE=splunk_heavy_forwarder
      - SPLUNK_START_ARGS=--accept-license
      - SPLUNK_PASSWORD=helloworld
      - SPLUNK_DSP_ENABLE=true
      - SPLUNK_DSP_CERT=auto
      - SPLUNK_DSP_SERVER=dsp-master-node.hostname:30001
      - SPLUNK_DSP_PIPELINE_NAME=ingest-example
      - SPLUNK_DSP_PIPELINE_DESC="Demo using forwarders as source"
      - SPLUNK_DSP_PIPELINE_SPEC='| from receive_from_forwarders("forwarders:all") | into index("", "main");'
    ports:
      - 8000
      - 8089
    volumes:
      - ./.scloud.toml:/home/splunk/.scloud.toml
      - ./.scloud_context:/home/splunk/.scloud_context
```

Alternatively, this can also be done using the `default.yml` as so:
```yaml
---
splunk:
  dsp:
    enable: True
    server: dsp-master-node.hostname:30001
    cert: auto
    pipeline_name: ingest-example
    pipeline_desc: "Demo using forwarders as source"
    pipeline_spec: '| from receive_from_forwarders("forwarders:all") | into index("", "main");'
  ...
```