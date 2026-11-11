"""Offline regressions for the same release policy and hash check used in CI."""

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from render_formula import render
from verify_release import WORKFLOW, metadata, verify_digest, verify_formula

TEMPLATE = Path(__file__).resolve().parents[2] / "templates/mosaik.rb.tmpl"


def formula(version="2.0.0", tag="mosaik-v2.0.0"):
    url = (f"https://github.com/Sakeliga/mosaic-homebrew/releases/download/"
           f"{tag}/mosaik-{version}.tar.gz")
    return (TEMPLATE.read_text().replace("{{url}}", url)
            .replace("{{sha256}}", "a" * 64).replace("{{version}}", version))


class ReleasePolicyTest(unittest.TestCase):
    def test_production_identity_is_exact_version(self):
        release = metadata(formula(), "main")
        self.assertEqual(release["identity_flag"], "--certificate-identity")
        self.assertEqual(release["identity"], f"{WORKFLOW}@refs/tags/v2.0.0")
        self.assertNotEqual(release["identity"], f"{WORKFLOW}@refs/tags/v2.0.1")

    def test_main_rejects_rehearsal_and_other_release(self):
        for tag in ("rehearsal-v2.0.0-123-1", "mosaik-v2.0.1", "mosaik-v2.0.0-rc.1"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                metadata(formula(tag=tag), "main")
        with self.assertRaises(ValueError):
            metadata(formula("2.0.0-rc.1", "mosaik-v2.0.0-rc.1"), "main")

    def test_rehearsal_only_accepts_rehearsal_workflow_identity(self):
        release = metadata(formula(tag="rehearsal-v2.0.0-123-1"), "rehearsal")
        self.assertEqual(release["identity_flag"], "--certificate-identity-regexp")
        self.assertRegex(f"{WORKFLOW}@refs/heads/rehearsal/cli-123", release["identity"])
        for identity in (f"{WORKFLOW}@refs/tags/v2.0.0", f"{WORKFLOW}@refs/heads/main",
                         f"{WORKFLOW}@refs/heads/rehearsal/", f"{WORKFLOW}@refs/heads/rehearsal-x",
                         f"{WORKFLOW.replace('Sakeliga', 'attacker')}@refs/heads/rehearsal/cli"):
            with self.subTest(identity=identity):
                self.assertIsNone(re.fullmatch(release["identity"], identity))
        with self.assertRaises(ValueError):
            metadata(formula(), "rehearsal")

    def test_rehearsal_requires_stable_version_run_id_and_attempt(self):
        for version, tag in (("2.0.0-rc.1", "rehearsal-v2.0.0-rc.1-123-1"),
                             ("2.0.0", "rehearsal-v2.0.0-123"),
                             ("2.0.0", "rehearsal-v2.0.1-123-1"),
                             ("2.0.0", "rehearsal-v2.0.0-abc-1"),
                             ("2.0.0", "rehearsal-v2.0.0-123-0")):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                metadata(formula(version, tag), "rehearsal")

    def test_untrusted_metadata_rejected(self):
        for text in (formula().replace("Sakeliga/", "attacker/"),
                     formula().replace("https://", "http://"),
                     formula().replace(".tar.gz\"", ".tar.gz?other\""),
                     formula() + '  sha256 "' + 'b' * 64 + '"\n',
                     formula().replace('mosaik-2.0.0.tar.gz', 'mosaik-#{system(\'bad\')}.tar.gz')):
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


class RenderingTest(unittest.TestCase):
    def test_formula_matches_template_and_infers_version(self):
        for base, tag in (("main", "mosaik-v2.0.0"),
                          ("rehearsal", "rehearsal-v2.0.0-123-2")):
            result = verify_formula(formula(tag=tag).encode(), TEMPLATE.read_bytes(), base)
            self.assertEqual(result["version"], "2.0.0")

    def test_added_ruby_changed_wrapper_or_newline_fails(self):
        original = formula().encode()
        for changed in (original + b'system "echo unexpected"\n',
                        original.replace(b"exec ", b"echo "),
                        original.rstrip(b"\n"),
                        original.replace(b'  license', b'  version "2.0.0"\n  license')):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "byte for byte"):
                verify_formula(changed, TEMPLATE.read_bytes(), "main")

    def test_repeated_optional_version_preserves_other_bytes(self):
        template = b"{{url}}\r\n{{sha256}}\n{{version}} {{version}}\n"
        release = metadata(formula(), "main")
        self.assertEqual(render(template, release["version"], release["url"], release["sha256"]),
                         (release["url"] + "\r\n" + "a" * 64 + "\n2.0.0 2.0.0\n").encode())

    def test_unknown_incomplete_missing_placeholders_and_unsafe_values_fail(self):
        release = metadata(formula(), "main")
        for template in (b"{{url}}", b"{{sha256}}", b"{{url}} {{sha256}} {{other}}",
                         b"{{url}} {{sha256}} {{", b"{{url}} {{sha256}} {{version "):
            with self.subTest(template=template), self.assertRaises(ValueError):
                render(template, release["version"], release["url"], release["sha256"])
        for version, url, sha in (("2.0.0-rc.1", release["url"], release["sha256"]),
                                  ("2.0.0", release["url"] + '\"\nsystem "bad"', release["sha256"]),
                                  ("2.0.0", release["url"], "xyz")):
            with self.subTest(version=version, url=url, sha=sha), self.assertRaises(ValueError):
                render(TEMPLATE.read_bytes(), version, url, sha)


if __name__ == "__main__":
    unittest.main()
