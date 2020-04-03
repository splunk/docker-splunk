## Architecture
From a design perspective, the containers brought up with the `docker-splunk` images are meant to provision themselves locally and asynchronously. The execution flow of the provisioning process is meant to gracefully handle interoperability in this manner, while also maintaining idempotency and reliability.

## Navigation

* [Networking](#networking)
* [Design](#design)
    * [Remote networking](#remote-networking)
* [Supported platforms](#supported-platforms)

## Networking
By default, the Docker image exposes a variety of ports for both external interaction as well as internal use.
```
EXPOSE 8000 8065 8088 8089 8191 9887 9997
```

Below is a table detailing the purpose of each port, which can be used as a reference for determining whether the port should be published for external consumption.

| Port Number | Description |
| --- | --- |
| 8000 | SplunkWeb UI |
| 8065 | Splunk app server |
| 8088 | HTTP Event Collector (HEC) |
| 8089 | SplunkD management port (REST API access) |
| 8191 | Key-value store replication |
| 9887 | Index replication |
| 9997 | Indexing/receiving |

## Design

#### Remote networking
Particularly when bringing up distributed Splunk topologies, there is a need for one Splunk instances to make a request against another Splunk instance in order to construct the cluster. These networking requests are often prone to failure, as when Ansible is executed asynchronously there are no guarantees that the requestee is online/ready to receive the message.

While developing new playbooks that require remote Splunk-to-Splunk connectivity, we employ the use of `retry` and `delay` options for tasks. For instance, in this example below, we add indexers as search peers of individual search head. To overcome error-prone networking, we have retry counts with delays embedded in the task. There are also break-early conditions that maintain idempotency so we can progress if successful:

<!-- {% raw %} -->
```yaml
- name: Set all indexers as search peers
  command: "{{ splunk.exec }} add search-server https://{{ item }}:{{ splunk.svc_port }} -auth {{ splunk.admin_user }}:{{ splunk.password }} -remoteUsername {{ splunk.admin_user }} -remotePassword {{ splunk.password }}"
  become: yes
  become_user: "{{ splunk.user }}"
  with_items: "{{ groups['splunk_indexer'] }}"
  register: set_indexer_as_peer
  until: set_indexer_as_peer.rc == 0 or set_indexer_as_peer.rc == 24
  retries: "{{ retry_num }}"
  delay: 3
  changed_when: set_indexer_as_peer.rc == 0
  failed_when: set_indexer_as_peer.rc != 0 and 'already exists' not in set_indexer_as_peer.stderr
  notify:
    - Restart the splunkd service
  no_log: "{{ hide_password }}"
  when: "'splunk_indexer' in groups"
```
<!-- {% endraw %} -->

Another utility you can add when creating new plays is an implicit wait. For more information on this, see the `roles/splunk_common/tasks/wait_for_splunk_instance.yml` play which will wait for another Splunk instance to be online before making any connections against it.

<!-- {% raw %} -->
```yaml
- name: Check Splunk instance is running
  uri:
    url: https://{{ splunk_instance_address }}:{{ splunk.svc_port }}/services/server/info?output_mode=json
    method: GET
    user: "{{ splunk.admin_user }}"
    password: "{{ splunk.password }}"
    validate_certs: false
  register: task_response
  until:
    - task_response.status == 200
    - lookup('pipe', 'date +"%s"')|int - task_response.json.entry[0].content.startup_time > 10
  retries: "{{ retry_num }}"
  delay: 3
  ignore_errors: true
  no_log: "{{ hide_password }}"
```
<!-- {% endraw %} -->

## Supported platforms
At the current time, this project only officially supports running Splunk Enterprise on `debian:stretch-slim`. We do have plans to incorporate other operating systems and Windows in the future.

