## Changelog

## Navigation

* [8.0.4](#804)
* [8.0.3](#803)
* [8.0.2.1](#8021)
* [8.0.2](#802)
* [8.0.1](#801)
* [8.0.0](#800)
* [7.3.5](#735)
* [7.3.4.2](#7342)
* [7.3.4](#734)
* [7.3.3](#733)
* [7.3.2](#732)
* [7.3.1](#731)
* [7.3.0](#730)
* [7.2.10.1](#72101)
* [7.2.10](#7210)
* [7.2.9](#729)
* [7.2.8](#728)
* [7.2.7](#727)
* [7.2.6](#726)
* [7.2.5.1](#7251)
* [7.2.5](#725)
* [7.2.4](#724)
* [7.2.3](#723)
* [7.2.2](#722)
* [7.2.1](#721)
* [7.2.0](#720)

---

## 8.0.4

#### What's New?
* Releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see [Fixed issues](https://docs.splunk.com/Documentation/Splunk/8.0.4/ReleaseNotes/Fixedissues) in 8.0.4.
* Additional tests for new features

#### splunk-ansible changes:
* Support for custom SSL certificates for the Splunkd management endpoint
* Support for custom ports for [Splunk Application Server](https://docs.splunk.com/Documentation/ITSI/latest/IModules/AboutApplicationServerModule) and [App KV Store](https://docs.splunk.com/Documentation/Splunk/latest/Admin/AboutKVstore) using:
    * `splunk.appserver.port`, `splunk.kvstore.port` in `default.yml`
    * `SPLUNK_APPSERVER_PORT`, `SPLUNK_KVSTORE_PORT` environment variables
* Java installation through `default.yml` with `java_download_url`, `java_update_version`, and `java_version`
* Support for Windows+AWS deployments for Splunk v7.2 and v7.3
* Set pass4SymmKey for indexer discovery separately from pass4SymmKey for indexer clustering with:
    * `splunk.idxc.discoveryPass4SymmKey` in `default.yml`
    * `SPLUNK_IDXC_DISCOVERYPASS4SYMMKEY` environment variable

---

## 8.0.3

#### What's New?
* Releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see [Fixed issues](https://docs.splunk.com/Documentation/Splunk/8.0.3/ReleaseNotes/Fixedissues) in 8.0.3.
* Limited `ansible-playbook` to `localhost` only
* Updated tests and documentation

#### splunk-ansible changes:
* Added support for custom SSL certificates for the HEC endpoint
* Added support for Java installations on Red Hat and CentOS
* Updated defaults for `service_name`
* Switched `splunk.conf` in `default.yml` from a dictionary mapping to an array-based scheme. The change is backwards compatible but moving to the new array-based type is highly recommended as the new standard.
* In S2S configuration, revised Splunk restart trigger to occur only when `splunktcp` has changed and Splunk is running
* Refactored how apps are copied and disabled
* Bugfix for supporting empty stanzas in config files

---

## 8.0.2.1

#### What's New?
* Releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see [Fixed issues](https://docs.splunk.com/Documentation/Splunk/8.0.2/ReleaseNotes/Fixedissues) in 8.0.2.1.
* Bugfixes and additional tests for new features

#### splunk-ansible changes:
* Added support for reading `SPLUNK_PASSWORD` from a file
* License master and cluster master URLs are now also configurable in the `default.yml` config, as well as with the `LICENSE_MASTER_URL` and `CLUSTER_MASTER_URL` environment variables
* Added support for auto-detecting the `service_name` for SplunkForwarder and allowing manual configuration with `splunk.service_name`
* All HEC related variables were revised to follow a nested dict format in `default.yml`, i.e. `splunk.hec_enableSSL` is now `splunk.hec.ssl`. See the [Provision HEC](https://github.com/splunk/splunk-ansible/blob/develop/docs/EXAMPLES.md#provision-hec) example in the docs.

---

## 8.0.2

#### What's New?
* New Splunk Enterprise release of 8.0.2

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/8.0.2/ReleaseNotes/Fixedissues
* Bugfixes and increasing test coverage for new features

#### splunk-ansible changes:
* Revised Splunk forwarding/receiving plays to optionally support SSL (see documentation on [securing data from forwarders](https://docs.splunk.com/Documentation/Splunk/latest/Security/Aboutsecuringdatafromforwarders))
* Initial support for forwarder management using [Splunk Monitoring Console](https://docs.splunk.com/Documentation/Splunk/latest/DMC/DMCoverview)
* New environment variables exposed to control replication/search factor for clusters, key/value pairs written to `splunk-launch.conf`, and replacing default security key (pass4SymmKey)

**NOTE** Changes made to support new features may break backwards-compatibility with former versions of the `default.yml` schema. This was deemed necessary for maintainability and extensibility for these additional features requested by the community. While we do test and make an effort to support previous schemas, it is strongly advised to regenerate the `default.yml` if you plan on upgrading to this version.

**DEPRECATION WARNING** As mentioned in the changelog, the environment variables `SPLUNK_SHC_SECRET` and `SPLUNK_IDXC_SECRET` will now be replaced by `SPLUNK_SHC_PASS4SYMMKEY` and `SPLUNK_IDXC_PASS4SYMMKEY` respectively. Both are currently supported and will be mapped to the same setting now, but in the future we will likely remove both `SPLUNK_SHC_SECRET` and `SPLUNK_IDXC_SECRET`

---

## 8.0.1

#### What's New?
* New Splunk Enterprise release of 8.0.1

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/8.0.1/ReleaseNotes/Fixedissues
* Bugfixes and increasing test coverage for new features

#### splunk-ansible changes:
* Service name fixes for AWS
* Bugfixes around forwarding and SHC-readiness
* Additional options to control SmartStore configuration
**NOTE** If you are currently using SmartStore, this change does break backwards-compatibility with former versions of the `default.yml` schema. This was necessary to expose the additional features asked for by the community. Please regenerate the `default.yml` if you plan on upgrading to this version.

---

## 8.0.0

#### What's New?
* New Splunk Enterprise release of 8.0.0

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/8.0.0/ReleaseNotes/Fixedissues
* Reduced base image size due to package management inflation
* Additional Python 2/Python 3 compatibility changes

#### splunk-ansible changes:
* Increasing delay intervals to better handle different platforms
* Adding vars needed for Ansible Galaxy
* Bugfix for pre-playbook tasks not supporting URLs

---

## 7.3.5

#### What's New?
* New Splunk Enterprise release of 7.3.5

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.5/ReleaseNotes/Fixedissues
* See [8.0.2.1](#8021) changes.

#### splunk-ansible changes:
* See [8.0.2.1](#8021) changes.

---

## 7.3.4.2

#### What's New?
* Releasing new images to support Splunk Enterprise maintenance patch.
* Bundling in changes to be consistent with the release of [8.0.2.1](#8021).

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.4/ReleaseNotes/Fixedissues
* See [8.0.2.1](#8021) changes.

#### splunk-ansible changes:
* See [8.0.2.1](#8021) changes.

---

## 7.3.4

#### What's New?
* New Splunk Enterprise release of 7.3.4

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.4/ReleaseNotes/Fixedissues
* See [8.0.1](#801) changes.

#### splunk-ansible changes:
* See [8.0.1](#801) changes.

---

## 7.3.3

#### What's New?
* New Splunk Enterprise release of 7.3.3

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.3/ReleaseNotes/Fixedissues
* Better management of deployment server apps
* Support for variety of Splunk package types
* Bugfixes around app installation

#### splunk-ansible changes:
* Removing unnecessary apps in distributed ITSI installations
* Partioning apps in serverclass.conf when using the deployment server
* Adding support for activating Splunk Free license on boot
* Support for cluster labels via environment variables
* Bugfixes around app installation (through default.yml and pathing)

---

## 7.3.2

#### What's New?
* New Splunk Enterprise release of 7.3.2

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.2/ReleaseNotes/Fixedissues
* Support for Redhat 8 UF on s390x
* Various bugfixes

#### splunk-ansible changes:
* Python 2 and Python 3 cross compatibility support
* Support SPLUNK_SECRET as an environment variable
* Prevent double-installation issue when SPLUNK_BUILD_URL is supplied
* Various bugfixes

---

## 7.3.1

#### What's New?
* New Splunk Enterprise release of 7.3.1

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.1/ReleaseNotes/Fixedissues
* Documentation update
* Minor bug fixes

#### splunk-ansible changes:
* Fixed Enterprise Security application installation issues
* Refactored Systemd
* Fixed Ansible formatting issue
* Cleaned up Python files before install

---

## 7.3.0

#### What's New?
* Adding base `debian-10` and `redhat-8` platform
* Changing default `splunk/splunk` from `debian-9` to `debian-10` for enhanced security
* Overarching changes to build structure to support multi-stage builds for various consumers

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.3.0/ReleaseNotes/Fixedissues
* Changing default `splunk/splunk` from `debian-9` to `debian-10` for enhanced security
* Overarching changes to build structure to support multi-stage builds for various consumers
* Minor documentation changes

#### splunk-ansible changes:
* Adding ability to dynamically change `SPLUNK_ROOT_ENDPOINT` at start-up time
* Adding ability to dynamically change SplunkWeb HTTP port at start-up time
* Modified manner in which deployment server installs + distributes app bundles
* More multi-site functionality
* Support for Cygwin-based Windows environments
* Minor documentation changes

---

## 7.2.10.1

#### What's New?
* New Splunk Enterprise maintenance patch of 7.2.10.1

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.10/ReleaseNotes/Fixedissues#Splunk_Enterprise_7.2.10.1
* See [8.0.3](#803) changes.

#### splunk-ansible changes:
* See [8.0.3](#803) changes.

---

## 7.2.10

#### What's New?
* New Splunk Enterprise release of 7.2.10

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.10/ReleaseNotes/Fixedissues
* See [8.0.2.1](#8021) changes.

#### splunk-ansible changes:
* See [8.0.2.1](#8021) changes.

---

## 7.2.9

#### What's New?
* Releasing new images to support Splunk Enterprise maintenance patch.
* Bundling in changes to be consistent with the release of [8.0.0](#800)

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.9/ReleaseNotes/Fixedissues
* See [8.0.0](#800) changes

#### splunk-ansible changes:
* See [8.0.0](#800) changes

---

## 7.2.8

#### What's New?
Nothing - releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.8/ReleaseNotes/Fixedissues

#### splunk-ansible changes:
* Nothing - releasing new images to support Splunk Enterprise maintenance patch

---

## 7.2.7

#### What's New?
* Adding base `debian-10` and `redhat-8` platform
* Changing default `splunk/splunk` from `debian-9` to `debian-10` for enhanced security
* Overarching changes to build structure to support multi-stage builds for various consumers

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.7/ReleaseNotes/Fixedissues
* Changing default `splunk/splunk` from `debian-9` to `debian-10` for enhanced security
* Overarching changes to build structure to support multi-stage builds for various consumers
* Minor documentation changes

#### splunk-ansible changes:
* Adding ability to dynamically change `SPLUNK_ROOT_ENDPOINT` at start-up time
* Adding ability to dynamically change SplunkWeb HTTP port at start-up time
* Modified manner in which deployment server installs + distributes app bundles
* More multi-site functionality
* Support for Cygwin-based Windows environments
* Minor documentation changes

---

## 7.2.6

#### What's New?
Nothing - releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.6/ReleaseNotes/Fixedissues

#### splunk-ansible changes:
* Nothing - releasing new images to support Splunk Enterprise maintenance patch

---

## 7.2.5.1

#### What's New?
Nothing - releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.5/ReleaseNotes/Fixedissues

#### splunk-ansible changes:
* Nothing - releasing new images to support Splunk Enterprise maintenance patch

---

## 7.2.5

#### What's New?
* Introducing multi-site to the party
* Added `splunk_deployment_server` role
* Minor bugfixes

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.5/ReleaseNotes/Fixedissues
* Documentation overhaul
* Adding initial framework to support multi-site deployments
* Removing built-in Docker stats app for Splunk Universal Forwarder due to lack of use and violation of permission model

#### splunk-ansible changes:
* Adding support for `splunk_deployment_server` role
* Adding initial framework to support multi-site deployments
* Small refactor of upgrade logic
* Ansible syntactic sugar and playbook clean-up
* Documentation overhaul
* Adding CircleCI to support automated regression testing

---

## 7.2.4

#### What's New?
* Support for Java installation in standalones and search heads
* Hardening of asyncronous SHC bootstrapping procedures
* App installation across all topologies
* Adding CircleCI to support automated regression testing
* Minor bugfixes

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.4/ReleaseNotes/Fixedissues
* Adding Clair scanner for automated security scanning
* Adding CircleCI to support automated regression testing
* Minor documentation changes

#### splunk-ansible changes:
* Changing replication port from 4001 to 9887 for PS and field best practices
* Adding support for multiple licenses via URL and filepath globs
* Adding support for java installation
* Hardening SHC-readiness during provisioning due to large-scale deployment syncronization issues
* Extracting out `admin` username to be dynamic and flexible and enabling it to be user-defined
* App installation support for distributed topologies (SHC, IDXC, etc.) and some primitive premium app support
* Supporting Splunk restart only when required (via Splunk internal restart_required check)
* Minor documentation changes

---

## 7.2.3

#### What's New?
Nothing - releasing new images to support Splunk Enterprise maintenance patch.

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.3/ReleaseNotes/Fixedissues

#### splunk-ansible changes:
* Nothing - releasing new images to support Splunk Enterprise maintenance patch

---

## 7.2.2

#### What's New?
* Permission model refactor
* Minor bugfixes

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.2/ReleaseNotes/Fixedissues
* Adding base `centos-7` platform
* Packages added to all base platforms: `acl` and `ping`
* Minor documentation changes
* Significant permission model refactor such that `splunkd` will be run under the `splunk:splunk` user/group and the `ansible-playbook` setup will be run under `ansible:ansible` user/group
* Introducing new environment variable `CONTAINER_ARTIFACT_DIR` for various artifacts

#### splunk-ansible changes:
* Writing ansible logs to container artifact directory
* Adding templates for various OS/distributions to define default `default.yml` settings
* Adding `no_log` to prevent password exposure
* Support new permission model with `become/become_user` elevation/de-elevation when interacting with `splunkd`
* Support for out-of-the-box SSL-enabled SplunkWeb
* Adding ability to generate any configuration file in `$SPLUNK_HOME/etc/system/local`
* Introducing user-defined pre- and post- playbook hooks that can run before and after (respectively) site.yml
* Minor documentation changes

---

## 7.2.1

#### What's New?
* Initial SmartStore support
* App installation for direct URL link, local tarball, and from SplunkBase for standalone and forwarder

#### docker-splunk changes:
* Bumping Splunk version. For details, see: https://docs.splunk.com/Documentation/Splunk/7.2.1/ReleaseNotes/Fixedissues
* Adding `python-requests` to base Docker image
* Adding app installation features (direct link, local tarball, and SplunkBase)
* Minor documentation changes

#### splunk-ansible changes:
* Minor documentation changes
* Introducing support for [SmartStore](https://docs.splunk.com/Documentation/Splunk/latest/Indexer/AboutSmartStore) and index creation via `defaults.yml`
* Checks for first-time run to drive idempotency
* Adding capability to enable boot-start of splunkd as a service
* Support for user-defined splunk.secret file
* Adding app installation features (direct link, local tarball, and SplunkBase)
* Fixing bug where HEC receiving was not enabled on various Splunk roles
* Ansible syntactic sugar and playbook clean-up
* Minor documentation changes

---

## 7.2.0

#### What's New?
Everything :)

#### docker-splunk changes:
* Initial release!
* Support for Splunk Enterprise and Splunk Universal Forwarder deployments on Docker
* Supporting standalone and distributed topologies

#### splunk-ansible changes:
* Initial release!
* Support for Splunk Enterprise and Splunk Universal Forwarder deployments on Docker
* Supporting standalone and distributed topologies
