## Changelog

## Navigation

* [7.3.0](#730)
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
