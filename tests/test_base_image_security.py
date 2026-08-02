import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYTHON_GPG_FINGERPRINT = "7169605F62C751356D054A26A821E680E5FA6305"
REDHAT_PLATFORMS = ("redhat-8", "redhat-9")


class TestBaseImageSecurity(unittest.TestCase):
    def test_redhat_python_signature_uses_verified_https_key(self):
        for platform in REDHAT_PLATFORMS:
            with self.subTest(platform=platform):
                base_dir = REPOSITORY_ROOT / "base" / platform
                dockerfile = (base_dir / "Dockerfile").read_text(encoding="utf-8")
                install_script = (base_dir / "install.sh").read_text(
                    encoding="utf-8"
                )

                self.assertIn(
                    f"PYTHON_GPG_FINGERPRINT={PYTHON_GPG_FINGERPRINT}",
                    dockerfile,
                )
                self.assertNotIn("PYTHON_GPG_KEY_ID", dockerfile)
                self.assertIn(
                    "https://keys.openpgp.org/vks/v1/by-fingerprint/"
                    "${PYTHON_GPG_FINGERPRINT}",
                    install_script,
                )
                self.assertIn("gpg --show-keys --with-colons", install_script)
                self.assertIn(
                    'actual_fingerprint" != "$PYTHON_GPG_FINGERPRINT',
                    install_script,
                )
                self.assertIn(
                    "gpg --batch --import /tmp/python-signing-key.asc",
                    install_script,
                )
                self.assertNotIn("--keyserver", install_script)


if __name__ == "__main__":
    unittest.main()
