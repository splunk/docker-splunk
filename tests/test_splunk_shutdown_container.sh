#!/usr/bin/env bash

# Copyright 2026 Splunk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

image="${1:-}"
if [[ -z "${image}" ]]; then
	echo "usage: $0 IMAGE" >&2
	exit 2
fi
if ! docker image inspect "${image}" >/dev/null 2>&1; then
	echo "shutdown qualification image is not available locally: ${image}" >&2
	exit 2
fi

runtime_root="$(mktemp -d /tmp/docker-splunk-shutdown-qualification.XXXXXX)"
case "${runtime_root}" in
	/tmp/docker-splunk-shutdown-qualification.*) ;;
	*)
		echo "refusing unexpected qualification directory: ${runtime_root}" >&2
		exit 1
		;;
esac

container_prefix="splunk-shutdown-qualification-$$"
containers=()
STARTED_CONTAINER=""
STARTED_CASE_DIR=""

cleanup() {
	local container
	for container in "${containers[@]}"; do
		docker rm -f "${container}" >/dev/null 2>&1 || true
	done
	docker run --rm \
		--user root \
		--entrypoint /bin/sh \
		-v "${runtime_root}:/qualification" \
		"${image}" \
		-c 'chmod -R a+rwX /qualification' >/dev/null 2>&1 || true
	rm -rf "${runtime_root}"
}
trap cleanup EXIT

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

assert_file_equals() {
	local path="$1"
	local expected="$2"
	[[ -f "${path}" ]] || fail "missing file ${path}"
	local actual
	actual="$(tr -d '\r\n' < "${path}")"
	[[ "${actual}" == "${expected}" ]] ||
		fail "${path} = ${actual@Q}, want ${expected@Q}"
}

assert_stop_called_once() {
	local case_dir="$1"
	[[ -f "${case_dir}/stop-calls" ]] ||
		fail "missing stop call log for ${case_dir}"
	local calls
	calls="$(wc -l < "${case_dir}/stop-calls" | tr -d ' ')"
	[[ "${calls}" == "1" ]] ||
		fail "stop call count = ${calls}, want 1"
	assert_file_equals "${case_dir}/stop-calls" "stop"
	assert_file_equals "${case_dir}/state-at-stop" "stopping"
}

prepare_case() {
	local scenario="$1"
	local stop_delay="$2"
	local stop_exit_code="$3"
	local case_dir="${runtime_root}/${scenario}"
	mkdir -p "${case_dir}/artifacts" "${case_dir}/splunk/bin"
	chmod 0777 "${case_dir}" "${case_dir}/artifacts" \
		"${case_dir}/splunk" "${case_dir}/splunk/bin"

	cat > "${case_dir}/splunk/bin/splunk" <<'FAKE_SPLUNK'
#!/bin/sh
cat "${CONTAINER_ARTIFACT_DIR}/splunk-container.state" > "${SPLUNK_TEST_STATE_AT_STOP}"
printf '%s\n' "$*" >> "${SPLUNK_TEST_CALL_LOG}"
trap 'exit 0' TERM
sleep "${SPLUNK_TEST_STOP_DELAY_SECONDS}"
exit "${SPLUNK_TEST_STOP_EXIT_CODE}"
FAKE_SPLUNK
	chmod 0755 "${case_dir}/splunk/bin/splunk"
	printf '%s\n' "${stop_delay}" > "${case_dir}/stop-delay"
	printf '%s\n' "${stop_exit_code}" > "${case_dir}/stop-exit-code"
	echo "${case_dir}"
}

start_case() {
	local scenario="$1"
	local stop_delay="$2"
	local stop_exit_code="$3"
	local timeout_seconds="$4"
	local case_dir
	case_dir="$(prepare_case "${scenario}" "${stop_delay}" "${stop_exit_code}")"
	local container="${container_prefix}-${scenario}"
	containers+=("${container}")

	docker run -d \
		--name "${container}" \
		-e CONTAINER_ARTIFACT_DIR=/qualification/artifacts \
		-e SPLUNK_HOME=/qualification/splunk \
		-e SPLUNK_USER=ansible \
		-e SPLUNK_SHUTDOWN_TIMEOUT_SECONDS="${timeout_seconds}" \
		-e SPLUNK_TEST_CALL_LOG=/qualification/stop-calls \
		-e SPLUNK_TEST_STATE_AT_STOP=/qualification/state-at-stop \
		-e SPLUNK_TEST_STOP_DELAY_SECONDS="${stop_delay}" \
		-e SPLUNK_TEST_STOP_EXIT_CODE="${stop_exit_code}" \
		-v "${case_dir}:/qualification" \
		"${image}" no-provision >/dev/null

	for _ in {1..20}; do
		if [[ "$(docker inspect --format '{{.State.Running}}' "${container}")" == "true" ]]; then
			STARTED_CONTAINER="${container}"
			STARTED_CASE_DIR="${case_dir}"
			return
		fi
		sleep 0.25
	done
	fail "container ${container} did not become running"
}

run_direct_term() {
	local container case_dir
	start_case direct-term 0 0 5
	container="${STARTED_CONTAINER}"
	case_dir="${STARTED_CASE_DIR}"
	docker stop --time 15 "${container}" >/dev/null
	docker logs "${container}" > "${case_dir}/container.log" 2>&1

	assert_file_equals "${case_dir}/artifacts/splunk-container.state" "stopping"
	assert_file_equals "${case_dir}/artifacts/splunk-shutdown.lock/result" "0"
	grep -q "source=term" \
		"${case_dir}/artifacts/splunk-shutdown.lock/owner" ||
		fail "direct TERM did not own shutdown"
	assert_stop_called_once "${case_dir}"
	grep -q "stop completed source=term result=0" "${case_dir}/container.log" ||
		fail "direct TERM completion was not logged"
	echo "PASS direct TERM"
}

run_prestop_then_term() {
	local container case_dir
	start_case prestop-term 0 0 5
	container="${STARTED_CONTAINER}"
	case_dir="${STARTED_CASE_DIR}"
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=prestop \
		> "${case_dir}/prestop.out" 2> "${case_dir}/prestop.err"
	if docker exec "${container}" /sbin/checkstate.sh \
		> "${case_dir}/checkstate.out" 2> "${case_dir}/checkstate.err"; then
		fail "stopping container remained ready"
	fi
	docker stop --time 15 "${container}" >/dev/null
	docker logs "${container}" > "${case_dir}/container.log" 2>&1

	assert_file_equals "${case_dir}/artifacts/splunk-shutdown.lock/result" "0"
	grep -q "source=prestop" \
		"${case_dir}/artifacts/splunk-shutdown.lock/owner" ||
		fail "preStop did not retain shutdown ownership"
	assert_stop_called_once "${case_dir}"
	grep -q "shutdown already completed result=0 source=term" \
		"${case_dir}/container.log" ||
		fail "TERM did not reuse the preStop result"
	echo "PASS preStop then TERM"
}

run_concurrent_callers() {
	local container case_dir
	start_case concurrent 2 0 5
	container="${STARTED_CONTAINER}"
	case_dir="${STARTED_CASE_DIR}"
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=prestop \
		> "${case_dir}/owner.out" 2> "${case_dir}/owner.err" &
	local owner_pid=$!

	for _ in {1..40}; do
		[[ -f "${case_dir}/artifacts/splunk-shutdown.lock/owner" ]] && break
		sleep 0.05
	done
	[[ -f "${case_dir}/artifacts/splunk-shutdown.lock/owner" ]] ||
		fail "concurrent owner was not recorded"
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=term \
		> "${case_dir}/follower.out" 2> "${case_dir}/follower.err"
	wait "${owner_pid}"
	docker stop --time 15 "${container}" >/dev/null

	assert_file_equals "${case_dir}/artifacts/splunk-shutdown.lock/result" "0"
	assert_stop_called_once "${case_dir}"
	grep -q "shutdown already in progress source=term" \
		"${case_dir}/follower.out" ||
		fail "concurrent follower did not observe the owner"
	echo "PASS concurrent callers"
}

run_failure_preservation() {
	local container case_dir
	start_case failure 0 7 5
	container="${STARTED_CONTAINER}"
	case_dir="${STARTED_CASE_DIR}"
	local first_result=0
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=prestop \
		> "${case_dir}/first.out" 2> "${case_dir}/first.err" ||
		first_result=$?
	local second_result=0
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=term \
		> "${case_dir}/second.out" 2> "${case_dir}/second.err" ||
		second_result=$?
	docker stop --time 15 "${container}" >/dev/null

	[[ "${first_result}" == "7" ]] ||
		fail "first failed stop returned ${first_result}, want 7"
	[[ "${second_result}" == "7" ]] ||
		fail "repeated failed stop returned ${second_result}, want 7"
	assert_file_equals "${case_dir}/artifacts/splunk-shutdown.lock/result" "7"
	assert_stop_called_once "${case_dir}"
	echo "PASS stop failure preservation"
}

run_timeout_preservation() {
	local container case_dir
	start_case timeout 20 0 1
	container="${STARTED_CONTAINER}"
	case_dir="${STARTED_CASE_DIR}"
	local first_result=0
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=prestop \
		> "${case_dir}/first.out" 2> "${case_dir}/first.err" ||
		first_result=$?
	local second_result=0
	docker exec "${container}" \
		/sbin/splunk-shutdown --source=term \
		> "${case_dir}/second.out" 2> "${case_dir}/second.err" ||
		second_result=$?
	docker stop --time 15 "${container}" >/dev/null

	[[ "${first_result}" == "124" ]] ||
		fail "timed-out stop returned ${first_result}, want 124"
	[[ "${second_result}" == "124" ]] ||
		fail "repeated timed-out stop returned ${second_result}, want 124"
	assert_file_equals "${case_dir}/artifacts/splunk-shutdown.lock/result" "124"
	assert_stop_called_once "${case_dir}"
	echo "PASS shutdown timeout preservation"
}

run_direct_term
run_prestop_then_term
run_concurrent_callers
run_failure_preservation
run_timeout_preservation

echo "PASS container shutdown qualification image=${image}"
