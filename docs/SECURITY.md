## Security ##
This section will cover various security considerations when using the Splunk Enterprise and Universal Forwarder containers.

### Startup Users ###

The Splunk Enterprise and Universal Forwarder containers may be started using one of the following three user accounts:

* `splunk` (most secure): This user has no privileged access and cannot use `sudo` to change to another user account. It is a member of the `ansible` group, which enables it to run the embedded playbooks at startup. When using the `splunk` user, all processes will run as this user. The `SPLUNK_HOME_OWNERSHIP_ENFORCEMENT` environment variable must be set to `false` when starting as this user. ***Recommended for production***

* `ansible` (middle ground): This user is a member of the `sudo` group and able to execute `sudo` commands without a password. It uses privileged access at startup only to perform certain actions which cannot be performed by regular users (see below). After startup, `sudo` access will automatically be removed from the `ansible` user if the environment variable `STEPDOWN_ANSIBLE_USER` is set to `true`. ***This is the default user account***

* `root` (least secure): This is a privileged user running with UID of `0`. Some customers may want to use this for forwarder processes that require access to log files which cannot be read by any other user. ***This is not recommended***

### After Startup ###

By default, the primary Splunk processes will always run as the unprivileged user and group `splunk`,
regardless of which user account the containers are started with. You can override this by changing the following:

* User: `splunk.user` variable in your `default.yml` template, or the `SPLUNK_USER` environment variable
* Group: `splunk.group` variable in your `default.yml` template, or the `SPLUNK_GROUP` environment variable

Note that the containers are built with the `splunk` user having UID `41812` and the `splunk` group having GID `41812`.

You may want to override these settings to ensure that Splunk forwarder processes have access to read your log files. For example, you can ensure that all processes run as `root` by starting as the `root` user with the environment variable `SPLUNK_USER` also set to `root` (this is not recommended).

### Privileged Features ###

Certain features supported by the Splunk Enterprise and Universal Forwarder containers require that they are started with privileged access using either the `ansible` or `root` user accounts.

#### Splunk Home Ownership ####

By default, at startup the containers will ensure that all files located under the `SPLUNK_HOME` directory (`/opt/splunk`) are owned by user `splunk` and group `splunk`. This helps to ensure that the Splunk processes are able to read and write any external volumes mounted for `/opt/splunk/etc` and `/opt/splunk/var`. While all supported versions of the docker engine will automatically set proper ownership for these volumes, external orchestration systems
typically will require extra steps.

If you know that this step is unnecessary, you can disable it by setting the `SPLUNK_HOME_OWNERSHIP_ENFORCEMENT` environment variable to `false`. This must be disabled when starting containers with the `splunk` user account.

#### Package Installation ####

The `JAVA_VERSION` environment variable can be used to automatically install OpenJDK at startup time. This feature requires starting as a privileged user account.

### Kubernetes Users ###

For Kubernetes, we recommend using the `fsGroup` [Security Context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/) to ensure that all Pods are able to write to your Persistent Volumes. For example:

```
apiVersion: v1
kind: Pod
metadata:
  name: example-splunk-pod
spec:
  securityContext:
    runAsUser: 41812
    fsGroup: 41812
  containers:
    name: example-splunk-container
    image: splunk/splunk
    env:
    - name: SPLUNK_HOME_OWNERSHIP_ENFORCEMENT
      value: "false"
...
```

This can be used to create a Splunk Enterprise Pod running as the unprivileged `splunk` user which is able to securely read and write from any Persistent Volumes that are created for it.

Red Hat OpenShift users can leverage the built-in `nonroot` [Security Context Constraint](https://docs.openshift.com/container-platform/3.9/admin_guide/manage_scc.html)
to run Pods with the above Security Context:
```
oc adm policy add-scc-to-user nonroot default
```