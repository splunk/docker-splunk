import pathlib
import re
import unittest


REPOSITORY = pathlib.Path(__file__).resolve().parents[1]
MAKEFILE = (REPOSITORY / "Makefile").read_text()
LOCKED_REQUIREMENTS = REPOSITORY / "tests" / "requirements.txt"
BOOTSTRAP_REQUIREMENTS = REPOSITORY / "tests" / "bootstrap-requirements.txt"


class TestTestBootstrap(unittest.TestCase):
    def test_make_uses_repository_virtual_environment(self):
        self.assertIn("TEST_VENV ?= $(CURDIR)/.test-venv", MAKEFILE)
        self.assertIn('"$(TEST_PYTHON)" -m venv "$(TEST_VENV)"', MAKEFILE)
        self.assertNotRegex(MAKEFILE, r"(?m)^\s+pip install ")

    def test_every_resolved_requirement_is_exactly_pinned(self):
        requirements = [
            line.strip()
            for line in LOCKED_REQUIREMENTS.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertTrue(requirements)
        self.assertTrue(all(re.match(r"^[A-Za-z0-9_.-]+==[^=]+$", line) for line in requirements))

    def test_legacy_compose_build_chain_is_constrained(self):
        locked = LOCKED_REQUIREMENTS.read_text().lower()
        bootstrap = BOOTSTRAP_REQUIREMENTS.read_text().lower()
        self.assertIn("docker-compose==1.29.2", locked)
        self.assertIn("pyyaml==5.4.1", locked)
        self.assertIn("cython==0.29.37", bootstrap)
        self.assertIn("pip==24.3.1", bootstrap)

    def test_image_pytest_targets_use_virtual_environment(self):
        invocations = [
            line
            for line in MAKEFILE.splitlines()
            if "$(TEST_PYTEST)" in line and " -n 2 " in line
        ]
        self.assertEqual(8, len(invocations))
        self.assertTrue(all('$(TEST_ENV) "$(TEST_PYTEST)"' in line for line in invocations))

    def test_virtual_environment_has_exact_cleanup_target(self):
        self.assertRegex(MAKEFILE, r'(?m)^test_clean:\n\trm -rf "\$\(TEST_VENV\)"$')


if __name__ == "__main__":
    unittest.main()
