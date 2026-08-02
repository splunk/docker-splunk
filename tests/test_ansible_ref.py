import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATED_SHC_ANSIBLE_REF = "a7af832c604f5fd9202e28f67261370ffe514402"


def run(command, cwd, check=True):
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class TestAnsibleRef(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp(prefix="docker-splunk-ansible-ref-"))
        self.source = self.tempdir / "source"
        self.build = self.tempdir / "build"
        self.source.mkdir()
        self.build.mkdir()
        shutil.copy(REPOSITORY_ROOT / "Makefile", self.build / "Makefile")

        run(["git", "init", "--quiet"], self.source)
        run(["git", "config", "user.name", "Docker Splunk Test"], self.source)
        run(["git", "config", "user.email", "docker-splunk-test@example.invalid"], self.source)

        (self.source / "content.txt").write_text("first\n", encoding="utf-8")
        run(["git", "add", "content.txt"], self.source)
        run(["git", "commit", "--quiet", "-m", "first"], self.source)
        self.first_commit = run(["git", "rev-parse", "HEAD"], self.source).stdout.strip()

        (self.source / "content.txt").write_text("second\n", encoding="utf-8")
        run(["git", "commit", "--quiet", "-am", "second"], self.source)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def make_ansible(self, expected_commit, check=True):
        return run(
            [
                "make",
                "ansible",
                f"SPLUNK_ANSIBLE_REPO={self.source}",
                f"SPLUNK_ANSIBLE_REF={expected_commit}",
            ],
            self.build,
            check=check,
        )

    def test_default_ref_is_validated_shc_commit(self):
        makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn(
            f"SPLUNK_ANSIBLE_REF ?= {VALIDATED_SHC_ANSIBLE_REF}",
            makefile,
        )
        self.assertNotIn(
            "SPLUNK_ANSIBLE_REF ?= $(SPLUNK_ANSIBLE_BRANCH)",
            makefile,
        )

    def test_checks_out_and_records_exact_commit(self):
        self.make_ansible(self.first_commit)

        checkout = self.build / "splunk-ansible"
        actual_commit = run(["git", "rev-parse", "HEAD"], checkout).stdout.strip()
        recorded_commit = (checkout / "version.txt").read_text(encoding="utf-8").strip()

        self.assertEqual(self.first_commit, actual_commit)
        self.assertEqual(self.first_commit, recorded_commit)

    def test_refuses_to_replace_local_changes(self):
        self.make_ansible(self.first_commit)
        checkout = self.build / "splunk-ansible"
        (checkout / "content.txt").write_text("local change\n", encoding="utf-8")

        result = self.make_ansible(self.first_commit, check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("contains local changes", result.stdout)

    def test_rejects_unreachable_ref(self):
        result = self.make_ansible("0" * 40, check=False)

        self.assertNotEqual(0, result.returncode)
        checkout = self.build / "splunk-ansible"
        self.assertFalse((checkout / "version.txt").exists())


if __name__ == "__main__":
    unittest.main()
