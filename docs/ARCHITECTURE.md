## Architecture
From a design perspective, the containers brought up with the `docker-splunk` images are meant to provision themselves locally and asynchronously. The execution flow of the provisioning process is meant to gracefully handle interoperability in this manner, while also maintaining idempotency and reliability. 

## Navigation

* [Design](#design)
    * [Remote networking](#remote-networking)
* [Supported platforms](#supported-platforms)

## Design

##### Remote networking 
Particularly when bringing up distributed Splunk topologies, there is a need for one Splunk instances to make a request against another Splunk instance in order to construct the cluster. These networking requests are often prone to failure, as when Ansible is executed asyncronously there are no guarantees that the requestee is online/ready to receive the message.

While developing new playbooks that require remote Splunk-to-Splunk connectivity, we employ the use of `retry` and `delay` options for tasks. For instance, in this example below, we add indexers as search peers of individual search head. To overcome error-prone networking, we have retry counts with delays embedded in the task. There are also break-early conditions that maintain idempotency so we can progress if successful:
```
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

Another utility you can add when creating new plays is an implicit wait. For more information on this, see the `roles/splunk_common/tasks/wait_for_splunk_instance.yml` play which will wait for another Splunk instance to be online before making any connections against it.
```
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

## Supported platforms
At the current time, this project only officially supports running Splunk Enterprise on `debian:stretch-slim`. We do have plans to incorporate other operating systems and Windows in the future.

