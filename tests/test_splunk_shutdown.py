#!/usr/bin/env python
# encoding: utf-8

import os
import pwd
import signal
import shutil
import subprocess
import tempfile
import time
import unittest


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHUTDOWN_SCRIPT = os.path.join(
    REPOSITORY_ROOT, "splunk", "common-files", "splunk-shutdown"
)


def make_runtime(stop_exit_code=0, stop_delay_seconds=0):
    runtime_dir = tempfile.mkdtemp(prefix="splunk-shutdown-test-")
    artifact_dir = os.path.join(runtime_dir, "artifacts")
    splunk_home = os.path.join(runtime_dir, "splunk")
    splunk_bin = os.path.join(splunk_home, "bin")
    os.makedirs(artifact_dir)
    os.makedirs(splunk_bin)

    call_log = os.path.join(runtime_dir, "stop-calls")
    state_at_stop = os.path.join(runtime_dir, "state-at-stop")
    fake_splunk = os.path.join(splunk_bin, "splunk")
    with open(fake_splunk, "w") as script:
        script.write(
            "#!/bin/sh\n"
            "cat \"${CONTAINER_ARTIFACT_DIR}/splunk-container.state\" "
            "> \"${SPLUNK_TEST_STATE_AT_STOP}\"\n"
            "printf '%s\\n' \"$*\" >> \"${SPLUNK_TEST_CALL_LOG}\"\n"
            "sleep \"${SPLUNK_TEST_STOP_DELAY_SECONDS}\"\n"
            "exit \"${SPLUNK_TEST_STOP_EXIT_CODE}\"\n"
        )
    os.chmod(fake_splunk, 0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "CONTAINER_ARTIFACT_DIR": artifact_dir,
            "SPLUNK_HOME": splunk_home,
            "SPLUNK_USER": pwd.getpwuid(os.getuid()).pw_name,
            "SPLUNK_SHUTDOWN_TIMEOUT_SECONDS": "10",
            "SPLUNK_TEST_CALL_LOG": call_log,
            "SPLUNK_TEST_STATE_AT_STOP": state_at_stop,
            "SPLUNK_TEST_STOP_DELAY_SECONDS": str(stop_delay_seconds),
            "SPLUNK_TEST_STOP_EXIT_CODE": str(stop_exit_code),
        }
    )
    return runtime_dir, artifact_dir, call_log, environment


def run_shutdown(environment, source="manual"):
    return subprocess.run(
        [SHUTDOWN_SCRIPT, "--source={}".format(source)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def read_text(path):
    with open(path, "r") as stream:
        return stream.read()


class SplunkShutdownTest(unittest.TestCase):

    def runtime(self, stop_exit_code=0, stop_delay_seconds=0):
        runtime = make_runtime(stop_exit_code, stop_delay_seconds)
        self.addCleanup(shutil.rmtree, runtime[0])
        return runtime

    def test_shutdown_records_stopping_and_runs_stop_once(self):
        _, artifact_dir, call_log, environment = self.runtime()

        first = run_shutdown(environment, "term")
        second = run_shutdown(environment, "prestop")

        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(
            read_text(os.path.join(artifact_dir, "splunk-container.state")),
            "stopping\n",
        )
        self.assertEqual(
            read_text(os.path.join(artifact_dir, "splunk-shutdown.lock", "result")),
            "0\n",
        )
        self.assertEqual(read_text(call_log).splitlines(), ["stop"])
        self.assertEqual(
            read_text(environment["SPLUNK_TEST_STATE_AT_STOP"]), "stopping\n"
        )
        self.assertIn(
            "source=term",
            read_text(os.path.join(artifact_dir, "splunk-shutdown.lock", "owner")),
        )

    def test_concurrent_callers_have_one_stop_owner(self):
        _, artifact_dir, call_log, environment = self.runtime(stop_delay_seconds=1)

        owner = subprocess.Popen(
            [SHUTDOWN_SCRIPT, "--source=prestop"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        owner_file = os.path.join(artifact_dir, "splunk-shutdown.lock", "owner")
        deadline = time.time() + 5
        while not os.path.exists(owner_file) and time.time() < deadline:
            time.sleep(0.01)

        follower = run_shutdown(environment, "term")
        owner_stdout, owner_stderr = owner.communicate(timeout=5)

        self.assertEqual(owner.returncode, 0, (owner_stdout, owner_stderr))
        self.assertEqual(follower.returncode, 0)
        self.assertIn("already in progress", follower.stdout)
        self.assertEqual(read_text(call_log).splitlines(), ["stop"])

    def test_stop_failure_is_preserved_without_second_stop(self):
        _, artifact_dir, call_log, environment = self.runtime(stop_exit_code=7)

        first = run_shutdown(environment, "prestop")
        second = run_shutdown(environment, "term")

        self.assertEqual(first.returncode, 7)
        self.assertEqual(second.returncode, 7)
        self.assertEqual(
            read_text(os.path.join(artifact_dir, "splunk-shutdown.lock", "result")),
            "7\n",
        )
        self.assertEqual(read_text(call_log).splitlines(), ["stop"])

    def test_stop_is_bounded_by_timeout(self):
        _, artifact_dir, call_log, environment = self.runtime(stop_delay_seconds=5)
        environment["SPLUNK_SHUTDOWN_TIMEOUT_SECONDS"] = "1"

        result = run_shutdown(environment, "term")

        self.assertEqual(result.returncode, 124)
        self.assertEqual(
            read_text(os.path.join(artifact_dir, "splunk-shutdown.lock", "result")),
            "124\n",
        )
        self.assertEqual(read_text(call_log).splitlines(), ["stop"])

    def test_invalid_timeout_is_rejected_before_ownership(self):
        _, artifact_dir, call_log, environment = self.runtime()
        environment["SPLUNK_SHUTDOWN_TIMEOUT_SECONDS"] = "not-a-number"

        result = run_shutdown(environment)

        self.assertEqual(result.returncode, 2)
        self.assertIn("positive integer", result.stderr)
        self.assertFalse(
            os.path.exists(os.path.join(artifact_dir, "splunk-shutdown.lock"))
        )
        self.assertFalse(os.path.exists(call_log))

    def test_image_and_term_handler_use_stable_shutdown_contract(self):
        entrypoint = read_text(
            os.path.join(
                REPOSITORY_ROOT, "splunk", "common-files", "entrypoint.sh"
            )
        )
        dockerfile = read_text(
            os.path.join(
                REPOSITORY_ROOT, "splunk", "common-files", "Dockerfile"
            )
        )

        self.assertIn("/sbin/splunk-shutdown --source=term", entrypoint)
        self.assertNotIn("${SPLUNK_HOME}/bin/splunk stop || true", entrypoint)
        self.assertIn("SPLUNK_SHUTDOWN_TIMEOUT_SECONDS", entrypoint)
        self.assertIn('"splunk/common-files/splunk-shutdown"', dockerfile)
        self.assertIn("/sbin/splunk-shutdown", dockerfile)
        self.assertIn("command -v timeout", dockerfile)

    def test_term_handler_exits_entrypoint_after_shutdown(self):
        runtime_dir = tempfile.mkdtemp(prefix="splunk-entrypoint-term-test-")
        self.addCleanup(shutil.rmtree, runtime_dir)
        shutdown_log = os.path.join(runtime_dir, "shutdown-calls")
        fake_shutdown = os.path.join(runtime_dir, "splunk-shutdown")
        with open(fake_shutdown, "w") as script:
            script.write(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >> \"{}\"\n"
                "exit 0\n".format(shutdown_log)
            )
        os.chmod(fake_shutdown, 0o755)

        entrypoint_copy = os.path.join(runtime_dir, "entrypoint.sh")
        entrypoint_source = read_text(
            os.path.join(
                REPOSITORY_ROOT, "splunk", "common-files", "entrypoint.sh"
            )
        )
        with open(entrypoint_copy, "w") as script:
            script.write(
                entrypoint_source.replace(
                    "/sbin/splunk-shutdown",
                    fake_shutdown,
                )
            )
        os.chmod(entrypoint_copy, 0o755)

        process = subprocess.Popen(
            [entrypoint_copy, "no-provision"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            start_new_session=True,
        )
        try:
            # Wait until the no-provision path is blocked in its long-running
            # wait, which matches the steady-state PID 1 behavior in the
            # container.
            time.sleep(1)
            process.send_signal(signal.SIGTERM)
            return_code = process.wait(timeout=5)
            self.assertEqual(return_code, 0)
            self.assertEqual(
                read_text(shutdown_log).splitlines(),
                ["--source=term"],
            )
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
