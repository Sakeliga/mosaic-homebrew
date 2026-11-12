"""Every platform's download is hashed and signature-checked; one bad file fails the release.

No real Sigstore signature exists offline. `cosign` here is a stand-in that
models the three things `cosign verify-blob` decides: the bundle covers these
exact bytes, the certificate identity is the expected one, and the issuer is
the expected one. The tests therefore show which identity this tap demands for
each file and that one refusal stops the release; real signatures are checked
by the same code in the rehearsal and release pull requests.
"""

import hashlib
import io
import json
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from render_formula import PLATFORMS
from test_verify_release import check
from verify_download import executable_matches, verify_contents, verify_downloads
from verify_release import ISSUER, WORKFLOW

STAND_IN = r'''
import hashlib, json, re, sys
arguments = sys.argv[1:]
assert arguments[0] == "verify-blob" and arguments[2] == "--bundle", arguments
blob, bundle_path, flag, identity = arguments[1], arguments[3], arguments[4], arguments[5]
assert arguments[6] == "--certificate-oidc-issuer" and len(arguments) == 8, arguments
assert bundle_path == blob + ".sigstore.json", arguments
try:
    bundle = json.load(open(bundle_path))
except OSError:
    sys.exit(1)
with open(sys.argv[0] + ".calls", "a") as calls:
    calls.write(json.dumps(arguments) + "\n")
if flag == "--certificate-identity":
    identity_matches = bundle["identity"] == identity
elif flag == "--certificate-identity-regexp":
    identity_matches = re.search(identity, bundle["identity"]) is not None
else:
    sys.exit(2)
signed = hashlib.sha256(open(blob, "rb").read()).hexdigest() == bundle["sha256"]
sys.exit(0 if signed and identity_matches and bundle["issuer"] == arguments[7] else 1)
'''


def header(platform):
    """The first bytes of a 64-bit executable for one platform, as its format defines them."""
    cpu = {"darwin-arm64": 0x0100000C, "darwin-x64": 0x01000007}
    machine = {"linux-x64": 62, "linux-arm64": 183}
    if platform in cpu:
        return struct.pack("<IIII", 0xFEEDFACF, cpu[platform], 0, 2) + bytes(16)
    return b"\x7fELF\x02\x01\x01" + bytes(9) + struct.pack("<HH", 2, machine[platform]) + bytes(12)


def tarball(platform=None, entries=None):
    """A flat gzip tarball; by default the three release files with this platform's executable."""
    if entries is None:
        entries = [("mosaik", header(platform) + f"binary for {platform}".encode()),
                   ("guide.md", b"guide\n"), ("LICENSE", b"licence\n")]
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, contents in entries:
            info = tarfile.TarInfo(name)
            if isinstance(contents, bytes):
                info.size, info.mode = len(contents), 0o755
                tar.addfile(info, io.BytesIO(contents))
            else:
                info.type, info.linkname = contents
                tar.addfile(info)
    return buffer.getvalue()


CJS = b"#!/usr/bin/env node\n\"use strict\";\nconsole.log(\"2.1.0\");\n"


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.cosign = self.root / "cosign"
        self.cosign.write_text(f"#!{sys.executable}\n{STAND_IN}")
        self.cosign.chmod(0o755)
        self.downloads = self.root / "release"
        self.downloads.mkdir()

    def release(self, base="main", tag="mosaik-v2.1.0", identity=f"{WORKFLOW}@refs/tags/v2.1.0",
                contents=tarball):
        """A verified proposal whose hashes are those of freshly written, signed stand-in files."""
        release = {**check(base, tag=tag), "mode": "release"}
        for asset in release["assets"]:
            data = contents(asset["platform"])
            (self.downloads / asset["asset"]).write_bytes(data)
            asset["sha256"] = hashlib.sha256(data).hexdigest()
            self.sign(asset["asset"], identity)
        return release

    def place(self, release, platform, data):
        """Put other bytes in one platform's slot, with a hash and signature that both pass."""
        name = f"mosaik-2.1.0-{platform}.tar.gz"
        (self.downloads / name).write_bytes(data)
        for asset in release["assets"]:
            if asset["platform"] == platform:
                asset["sha256"] = hashlib.sha256(data).hexdigest()
        self.sign(name, f"{WORKFLOW}@refs/tags/v2.1.0")

    def sign(self, name, identity, issuer=ISSUER):
        contents = (self.downloads / name).read_bytes()
        (self.downloads / (name + ".sigstore.json")).write_text(json.dumps(
            {"identity": identity, "issuer": issuer, "sha256": hashlib.sha256(contents).hexdigest()}))

    def verify(self, release):
        verify_downloads(release, self.downloads, cosign=str(self.cosign))

    def calls(self):
        log = Path(str(self.cosign) + ".calls")
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_all_platforms_are_hashed_and_signature_checked_with_the_exact_identity(self):
        release = self.release()
        self.verify(release)
        calls = self.calls()
        self.assertEqual([Path(call[1]).name for call in calls],
                         [f"mosaik-2.1.0-{platform}.tar.gz" for platform in PLATFORMS])
        for call in calls:
            self.assertEqual(call[4:], ["--certificate-identity", f"{WORKFLOW}@refs/tags/v2.1.0",
                                        "--certificate-oidc-issuer", ISSUER])

    def test_one_platform_with_a_wrong_sha256_fails(self):
        for platform in PLATFORMS:
            release = self.release()
            for asset in release["assets"]:
                if asset["platform"] == platform:
                    asset["sha256"] = "0" * 64
            with self.subTest(platform=platform), \
                    self.assertRaisesRegex(ValueError, f"mosaik-2.1.0-{platform}.tar.gz: sha256 mismatch"):
                self.verify(release)

    def test_one_changed_or_swapped_file_fails(self):
        for platform in PLATFORMS:
            release = self.release()
            (self.downloads / f"mosaik-2.1.0-{platform}.tar.gz").write_bytes(b"changed after signing")
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                self.verify(release)
        release = self.release()
        first, second = (self.downloads / f"mosaik-2.1.0-{platform}.tar.gz" for platform in PLATFORMS[:2])
        swapped = first.read_bytes(), second.read_bytes()
        second.write_bytes(swapped[0])
        first.write_bytes(swapped[1])
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            self.verify(release)

    def test_one_file_signed_for_another_tag_or_identity_fails(self):
        others = (f"{WORKFLOW}@refs/tags/v2.0.0",
                  f"{WORKFLOW}@refs/tags/v2.1.1",
                  f"{WORKFLOW}@refs/heads/main",
                  f"{WORKFLOW}@refs/heads/rehearsal/cli",
                  f"{WORKFLOW.replace('deploy.yml', 'other.yml')}@refs/tags/v2.1.0",
                  f"{WORKFLOW.replace('Sakeliga', 'attacker')}@refs/tags/v2.1.0")
        for platform in PLATFORMS:
            for other in others:
                release = self.release()
                self.sign(f"mosaik-2.1.0-{platform}.tar.gz", other)
                with self.subTest(platform=platform, other=other), \
                        self.assertRaises(subprocess.CalledProcessError):
                    self.verify(release)

    def test_one_file_with_another_issuer_or_a_signature_over_other_bytes_fails(self):
        for platform in PLATFORMS:
            name = f"mosaik-2.1.0-{platform}.tar.gz"
            release = self.release()
            self.sign(name, f"{WORKFLOW}@refs/tags/v2.1.0", issuer="https://accounts.example.com")
            with self.subTest(platform=platform, case="issuer"), \
                    self.assertRaises(subprocess.CalledProcessError):
                self.verify(release)
            release = self.release()
            bundle = self.downloads / (name + ".sigstore.json")
            bundle.write_text(json.dumps({**json.loads(bundle.read_text()), "sha256": "0" * 64}))
            with self.subTest(platform=platform, case="bytes"), \
                    self.assertRaises(subprocess.CalledProcessError):
                self.verify(release)

    def test_rehearsal_accepts_only_rehearsal_branch_identities_for_every_file(self):
        tag = "rehearsal-v2.1.0-123-1"
        release = self.release("rehearsal", tag, f"{WORKFLOW}@refs/heads/rehearsal/006")
        self.verify(release)
        for call in self.calls():
            self.assertEqual(call[4], "--certificate-identity-regexp")
        for platform in PLATFORMS:
            for other in (f"{WORKFLOW}@refs/tags/v2.1.0", f"{WORKFLOW}@refs/heads/main"):
                release = self.release("rehearsal", tag, f"{WORKFLOW}@refs/heads/rehearsal/006")
                self.sign(f"mosaik-2.1.0-{platform}.tar.gz", other)
                with self.subTest(platform=platform, other=other), \
                        self.assertRaises(subprocess.CalledProcessError):
                    self.verify(release)

    def test_missing_file_or_bundle_fails(self):
        for platform in PLATFORMS:
            name = f"mosaik-2.1.0-{platform}.tar.gz"
            release = self.release()
            (self.downloads / (name + ".sigstore.json")).unlink()
            with self.subTest(platform=platform, missing="bundle"), \
                    self.assertRaises(subprocess.CalledProcessError):
                self.verify(release)
            release = self.release()
            (self.downloads / name).unlink()
            with self.subTest(platform=platform, missing="archive"), self.assertRaises(FileNotFoundError):
                self.verify(release)

    def test_another_platforms_signed_tarball_in_a_slot_fails(self):
        for slot in PLATFORMS:
            for other in PLATFORMS:
                if other == slot:
                    continue
                release = self.release()
                self.place(release, slot, tarball(other))
                with self.subTest(slot=slot, holds=other), \
                        self.assertRaisesRegex(ValueError, f"not a 64-bit executable for {slot}"):
                    self.verify(release)

    def test_one_signed_file_in_every_slot_fails(self):
        for platform in PLATFORMS:
            release = self.release(contents=lambda _slot, platform=platform: tarball(platform))
            with self.subTest(everywhere=platform), self.assertRaisesRegex(ValueError, "not a 64-bit executable"):
                self.verify(release)

    def test_the_signed_cjs_in_a_tarball_slot_fails(self):
        for slot in PLATFORMS:
            release = self.release()
            self.place(release, slot, CJS)
            with self.subTest(slot=slot, case="the .cjs itself"), \
                    self.assertRaisesRegex(ValueError, "not a readable gzip tarball"):
                self.verify(release)
            release = self.release()
            self.place(release, slot, tarball(entries=[("mosaik", CJS), ("guide.md", b"g"), ("LICENSE", b"l")]))
            with self.subTest(slot=slot, case="the .cjs named mosaik"), \
                    self.assertRaisesRegex(ValueError, "not a 64-bit executable"):
                self.verify(release)

    def test_tarball_must_hold_exactly_the_three_regular_files(self):
        slot = PLATFORMS[0]
        binary, guide, licence = ("mosaik", header(slot)), ("guide.md", b"g"), ("LICENSE", b"l")
        cases = {
            "extra file": ([binary, guide, licence, ("postinstall.sh", b"x")], "unexpected or repeated"),
            "nested file": ([binary, guide, licence, ("bin/mosaik", header(slot))], "unexpected or repeated"),
            "dot prefix": ([("./mosaik", header(slot)), guide, licence], "unexpected or repeated"),
            "repeated binary": ([binary, guide, licence, binary], "unexpected or repeated"),
            "missing guide": ([binary, licence], "missing guide.md"),
            "missing binary": ([guide, licence], "missing mosaik"),
            "empty": ([], "missing"),
            "symlinked binary": ([("mosaik", (tarfile.SYMTYPE, "/bin/sh")), guide, licence], "not a regular file"),
            "hard-linked licence": ([binary, guide, ("LICENSE", (tarfile.LNKTYPE, "mosaik"))], "not a regular file"),
            "directory": ([binary, guide, ("LICENSE", (tarfile.DIRTYPE, ""))], "not a regular file"),
        }
        for case, (entries, message) in cases.items():
            release = self.release()
            self.place(release, slot, tarball(entries=entries))
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, message):
                self.verify(release)
        release = self.release()
        self.place(release, slot, tarball(slot)[:len(tarball(slot)) // 2])
        with self.subTest(case="truncated"), self.assertRaisesRegex(ValueError, "not a readable gzip tarball"):
            self.verify(release)

    def test_executable_header_is_exact_for_each_platform(self):
        for platform in PLATFORMS:
            good = header(platform)
            self.assertTrue(executable_matches(good, platform))
            self.assertEqual([other for other in PLATFORMS if executable_matches(good, other)], [platform])
            for bad in (b"", good[:8], bytes(32), CJS, b"\xca\xfe\xba\xbe" + good[4:]):
                with self.subTest(platform=platform, bad=bad):
                    self.assertFalse(executable_matches(bad, platform))
            self.assertFalse(executable_matches(good, "windows-x64"))
            self.assertFalse(executable_matches(good, platform.split("-")[0] + "-riscv64"))
        mach, elf = header("darwin-arm64"), bytearray(header("linux-x64"))
        self.assertFalse(executable_matches(struct.pack("<I", 0xFEEDFACE) + mach[4:], "darwin-arm64"))  # 32-bit
        self.assertFalse(executable_matches(mach[:12] + struct.pack("<I", 6) + mach[16:], "darwin-arm64"))  # dylib
        for offset, value, reason in ((4, 1, "32-bit"), (5, 2, "big-endian"), (16, 1, "object file")):
            changed = bytearray(elf)
            changed[offset] = value
            with self.subTest(reason=reason):
                self.assertFalse(executable_matches(bytes(changed), "linux-x64"))
        elf[16] = 3
        self.assertTrue(executable_matches(bytes(elf), "linux-x64"))  # position-independent executable

    def test_contents_are_checked_only_after_hash_and_signature(self):
        release = self.release()
        slot = PLATFORMS[0]
        name = f"mosaik-2.1.0-{slot}.tar.gz"
        (self.downloads / name).write_bytes(tarball(PLATFORMS[1]))
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            self.verify(release)
        verify_contents(self.downloads / f"mosaik-2.1.0-{PLATFORMS[1]}.tar.gz", PLATFORMS[1])

    def test_static_proposals_and_empty_releases_are_refused(self):
        release = self.release()
        for changed in ({"mode": "static"}, {"assets": []}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.verify({**release, **changed})


if __name__ == "__main__":
    unittest.main()
