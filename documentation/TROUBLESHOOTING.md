## Troubleshooting ##
**Note:** Splunk Support only provides support for the single instance Splunk Validated Architectures (S-Type). For all other configurations, please contact Splunk Professional Services.

#### Validate your environment ####
The most important step in troubleshooting is to validate the environment.
Please ensure that the following questions are answered:
* Is Docker installed properly?  Can it run simple Linux images, such as CentOS or Ubuntu?
* Is the latest Splunk image downloaded or are you using an older image?  Do the image hashes match?
* Is Docker running?
* Are there any settings that could influence or limit the container's behavior?
* Are there other containers which could impact running the Splunk containers (i.e. noisy neighbors)?
#### Validate the Splunk settings ####
Please refer to the [Setup page](SETUP.md) for comprehensive documentation on the different settings.
* Make sure that variable names are spelled correctly
* Make sure that the variable values are spelled correctly
* Make sure that paths and URLs referenced by the variables exist
#### Check the docker logs ####
Check error messages by running the following command:
```
$ docker logs <container name>
```
This will print out any log messages produced by the container.
##### Connecting an interactive shell to the container #####
You can start an interactive shell to enter the container:
```
$ docker exec -it <container-id> /bin/bash
```

#### Producing a Splunk Enterprise Diag ####
Verify the container is still up and running using `docker ps`:
```
docker ps --all
```
```
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS                   PORTS                                                                                     NAMES
52f0fa2958a5        splunk-debian-9     "/sbin/entrypoint.sh…"   14 minutes ago      Up 9 minutes (healthy)   4001/tcp, 8065/tcp, 8088-8089/tcp, 8191/tcp, 9887/tcp, 9997/tcp, 0.0.0.0:8000->8000/tcp   nostalgic_bardeen
```
in the event the container is not in a "healthy" status, or is no longer running, please start the container:
```
docker start <container-id>
```

Once you've verified the container is running, connect to it either through an [interactive shell](Connecting an interactive shell to the container), or by using `docker exec`.
If you've used an interactive shell or have access to the Splunk GUI, please use the [Generate a diagnostic file](http://docs.splunk.com/Documentation/Splunk/7.1.2/Troubleshooting/Generateadiag) documentation from docs.splunk.com.

Call `splunk diag` direct without an interactive shell by running the following:

```
docker exec ${SPLUNK_HOME}/bin/splunk diag 
```
Please reference [Generate a diagnostic file](http://docs.splunk.com/Documentation/Splunk/7.1.2/Troubleshooting/Generateadiag) for any additonal flags you may wish to set.
If your Docker container / hosts have access to Splunk.com, you can now send the file directly to Splunk Support by using the following command:
```
docker exec ${SPLUNK_HOME}/bin/splunk diag --upload --case-number=<case_num> --upload-user=<your_splunk_id> --upload-password=<passwd> --upload-description="Monday diag, as requested.
```
If your instance does not have direct access, you can pull the diag using `docker cp`:
```
docker cp <container-id>:/opt/splunk/var/run/diags/<filename> <location on your local docker client>
```

#### Creating a health check in your container ####
You can also automate container monitoring within the Splunk Enterprise container itself by creating a new image layer and adding a `HEALTHCHECK`.  An example healthcheck would look like this:
```
HEALTHCHECK --interval=30s --timeout=30s --start-period=3m --retries=5 CMD /sbin/checkstate.sh || exit 1
```
Where `checkstate.sh` attempts to connect to port 8000.

Please consult Docker's website for more information.


