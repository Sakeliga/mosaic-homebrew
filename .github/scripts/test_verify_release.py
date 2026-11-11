"""Offline regressions for the same release policy and hash check used in CI."""

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from verify_release import WORKFLOW, metadata, verify_digest


def formula(version="2.0.0", tag="mosaik-v2.0.0"):
    return (f'  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/'
            f'{tag}/mosaik-{version}.tar.gz"\n  version "{version}"\n'
            f'  sha256 "{"a" * 64}"\n')


class ReleasePolicyTest(unittest.TestCase):
    def test_production_identity_is_exact_version(self):
        release = metadata(formula(), "main")
        self.assertEqual(release["identity_flag"], "--certificate-identity")
        self.assertEqual(release["identity"], f"{WORKFLOW}@refs/tags/v2.0.0")
        self.assertNotEqual(release["identity"], f"{WORKFLOW}@refs/tags/v2.0.1")

    def test_main_rejects_rehearsal_and_other_release(self):
        for tag in ("rehearsal-v2.0.0-123", "mosaik-v2.0.1", "mosaik-v2.0.0-rc.1"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                metadata(formula(tag=tag), "main")
        with self.assertRaises(ValueError):
            metadata(formula("2.0.0-rc.1", "mosaik-v2.0.0-rc.1"), "main")

    def test_rehearsal_only_accepts_rehearsal_workflow_identity(self):
        release = metadata(formula(tag="rehearsal-v2.0.0-123"), "rehearsal")
        self.assertEqual(release["identity_flag"], "--certificate-identity-regexp")
        self.assertRegex(f"{WORKFLOW}@refs/heads/rehearsal/cli-123", release["identity"])
        for identity in (f"{WORKFLOW}@refs/tags/v2.0.0", f"{WORKFLOW}@refs/heads/main",
                         f"{WORKFLOW}@refs/heads/rehearsal/", f"{WORKFLOW}@refs/heads/rehearsal-x",
                         f"{WORKFLOW.replace('Sakeliga', 'attacker')}@refs/heads/rehearsal/cli"):
            with self.subTest(identity=identity):
                self.assertIsNone(re.fullmatch(release["identity"], identity))
        with self.assertRaises(ValueError):
            metadata(formula(), "rehearsal")

    def test_rehearsal_prerelease(self):
        self.assertEqual(metadata(formula("2.0.0-rc.1", "rehearsal-v2.0.0-rc.1-123"),
                                  "rehearsal")["version"], "2.0.0-rc.1")

    def test_untrusted_metadata_rejected(self):
        for text in (formula().replace("Sakeliga/", "attacker/"),
                     formula().replace("https://", "http://"),
                     formula().replace(".tar.gz\"", ".tar.gz?other\""),
                     formula() + '  version "9.9.9"\n',
                     formula().replace('version "2.0.0"', 'version "#{system(\'bad\')}"')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                metadata(text, "main")
        with self.assertRaises(ValueError):
            metadata(formula(), "feature")

    def test_hash_accepts_original_rejects_wrong_hash_and_changed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "release.tar.gz"
            archive.write_bytes(b"release bytes")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            verify_digest(archive, digest)
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                verify_digest(archive, "0" * 64)
            archive.write_bytes(b"changed release bytes")
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                verify_digest(archive, digest)


if __name__ == "__main__":
    unittest.main()
