"""Offline regressions for the same release policy and hash check used in CI."""

import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from render_formula import PLATFORMS, example_values, patterns, placeholder, render
from verify_release import WORKFLOW, extract, metadata, verify_digest, verify_formula

SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS.parents[1] / "templates/mosaik.rb.tmpl"
RELEASES = "https://github.com/Sakeliga/mosaic-homebrew/releases/download/"


def url(platform, version="2.1.0", tag="mosaik-v2.1.0"):
    return f"{RELEASES}{tag}/mosaik-{version}-{platform}.tar.gz"


def values(version="2.1.0", tag="mosaik-v2.1.0"):
    """One distinct, well-formed sha256 per platform, so a swap cannot pass unnoticed."""
    result = {"version": version}
    for index, platform in enumerate(PLATFORMS):
        result[placeholder("url", platform)] = url(platform, version, tag)
        result[placeholder("sha256", platform)] = f"{index + 10:x}" * 64
    return result


def formula(version="2.1.0", tag="mosaik-v2.1.0", **changed):
    """The template with literal substitution and no validation, as a proposer could write it."""
    text = TEMPLATE.read_text()
    for name, value in {**values(version, tag), **changed}.items():
        text = text.replace("{{" + name + "}}", value)
    return text.encode()


def check(base="main", **arguments):
    return verify_formula(formula(**arguments), TEMPLATE.read_bytes(), base)


class ReleasePolicyTest(unittest.TestCase):
    def test_production_identity_is_exact_version(self):
        release = check()
        self.assertEqual(release["identity_flag"], "--certificate-identity")
        self.assertEqual(release["identity"], f"{WORKFLOW}@refs/tags/v2.1.0")
        self.assertNotEqual(release["identity"], f"{WORKFLOW}@refs/tags/v2.1.1")
        self.assertEqual(release["tag"], "mosaik-v2.1.0")

    def test_every_platform_is_reported_with_its_own_url_and_hash(self):
        release = check()
        self.assertEqual([asset["platform"] for asset in release["assets"]], list(PLATFORMS))
        expected = values()
        for asset in release["assets"]:
            platform = asset["platform"]
            self.assertEqual(asset["asset"], f"mosaik-2.1.0-{platform}.tar.gz")
            self.assertEqual(asset["url"], expected[placeholder("url", platform)])
            self.assertEqual(asset["sha256"], expected[placeholder("sha256", platform)])
        self.assertEqual(len({asset["sha256"] for asset in release["assets"]}), len(PLATFORMS))

    def test_main_rejects_rehearsal_and_other_release(self):
        for tag in ("rehearsal-v2.1.0-123-1", "mosaik-v2.1.1", "mosaik-v2.1.0-rc.1"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                check(tag=tag)
        with self.assertRaises(ValueError):
            check(version="2.1.0-rc.1", tag="mosaik-v2.1.0-rc.1")

    def test_rehearsal_only_accepts_rehearsal_workflow_identity(self):
        release = check("rehearsal", tag="rehearsal-v2.1.0-123-1")
        self.assertEqual(release["identity_flag"], "--certificate-identity-regexp")
        self.assertRegex(f"{WORKFLOW}@refs/heads/rehearsal/cli-123", release["identity"])
        for identity in (f"{WORKFLOW}@refs/tags/v2.1.0", f"{WORKFLOW}@refs/heads/main",
                         f"{WORKFLOW}@refs/heads/rehearsal/", f"{WORKFLOW}@refs/heads/rehearsal-x",
                         f"{WORKFLOW.replace('Sakeliga', 'attacker')}@refs/heads/rehearsal/cli"):
            with self.subTest(identity=identity):
                self.assertIsNone(re.fullmatch(release["identity"], identity))
        with self.assertRaises(ValueError):
            check("rehearsal")

    def test_rehearsal_requires_stable_version_run_id_and_attempt(self):
        for version, tag in (("2.1.0-rc.1", "rehearsal-v2.1.0-rc.1-123-1"),
                             ("2.1.0", "rehearsal-v2.1.0-123"),
                             ("2.1.0", "rehearsal-v2.1.1-123-1"),
                             ("2.1.0", "rehearsal-v2.1.0-abc-1"),
                             ("2.1.0", "rehearsal-v2.1.0-123-0")):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                check("rehearsal", version=version, tag=tag)

    def test_only_canonical_versions_are_accepted(self):
        for version in ("2.010.0", "02.1.0", "2.1.00", "2.01.0", "00.0.0", "2.1.0.0", "2.1", "v2.1.0"):
            tag = f"mosaik-v{version}"
            with self.subTest(version=version, where="everywhere"), self.assertRaises(ValueError):
                check(version=version, tag=tag)
            with self.subTest(version=version, where="version line"), self.assertRaises(ValueError):
                check(version=version)
            with self.subTest(version=version, where="tag"), self.assertRaises(ValueError):
                check(tag=tag)
            with self.subTest(version=version, where="rehearsal"), self.assertRaises(ValueError):
                check("rehearsal", version=version, tag=f"rehearsal-v{version}-123-1")
            for platform in PLATFORMS:
                changed = {placeholder("url", platform): url(platform, version=version)}
                with self.subTest(version=version, where=platform), self.assertRaises(ValueError):
                    check(**changed)
            with self.subTest(version=version, where="render"), self.assertRaisesRegex(ValueError, "invalid version"):
                render(TEMPLATE.read_bytes(), {**values(), "version": version})
        for version in ("0.0.0", "2.10.0", "10.20.30", "2.0.10"):
            with self.subTest(version=version):
                self.assertEqual(check(version=version, tag=f"mosaik-v{version}")["version"], version)

    def test_one_platform_naming_another_tag_fails(self):
        for platform in PLATFORMS:
            for base, good, other in (("main", "mosaik-v2.1.0", "mosaik-v2.0.0"),
                                      ("main", "mosaik-v2.1.0", "rehearsal-v2.1.0-123-1"),
                                      ("rehearsal", "rehearsal-v2.1.0-123-1", "rehearsal-v2.1.0-124-1"),
                                      ("rehearsal", "rehearsal-v2.1.0-123-1", "mosaik-v2.1.0")):
                changed = {placeholder("url", platform): url(platform, tag=other)}
                with self.subTest(platform=platform, other=other), \
                        self.assertRaisesRegex(ValueError, "same release tag"):
                    check(base, tag=good, **changed)

    def test_one_platform_naming_another_version_fails(self):
        for platform in PLATFORMS:
            changed = {placeholder("url", platform): url(platform, version="2.0.9")}
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, "same version"):
                check(**changed)

    def test_version_line_must_equal_the_urls_version(self):
        with self.assertRaisesRegex(ValueError, "must equal the version in its URLs"):
            check(version="2.1.0", **{name: value for name, value in values("2.0.9", "mosaik-v2.0.9").items()
                                      if name != "version"})

    def test_url_platform_must_match_its_placeholder(self):
        for platform in PLATFORMS:
            for other in PLATFORMS:
                if other == platform:
                    continue
                changed = {placeholder("url", platform): url(other)}
                with self.subTest(placeholder=platform, url=other), self.assertRaises(ValueError):
                    check(**changed)
        swapped = values()
        first, second = placeholder("url", PLATFORMS[0]), placeholder("url", PLATFORMS[1])
        swapped[first], swapped[second] = swapped[second], swapped[first]
        with self.assertRaises(ValueError):
            check(**swapped)

    def test_untrusted_metadata_rejected_for_any_one_platform(self):
        for platform in PLATFORMS:
            good = url(platform)
            name = placeholder("url", platform)
            for bad in (good.replace("Sakeliga/", "attacker/"),
                        good.replace("https://", "http://"),
                        good + "?other",
                        good.replace(".tar.gz", ".zip"),
                        good.replace(f"-{platform}", ""),
                        good.replace("mosaik-2.1.0-", "mosaik-#{system('bad')}-"),
                        good + '"\n      system "bad'):
                with self.subTest(platform=platform, bad=bad), self.assertRaises(ValueError):
                    check(**{name: bad})
            for bad in ("xyz", "A" * 64, "a" * 63, "a" * 65):
                with self.subTest(platform=platform, sha256=bad), self.assertRaises(ValueError):
                    check(**{placeholder("sha256", platform): bad})
        with self.assertRaises(ValueError):
            check("feature")

    def test_policy_rechecks_values_without_the_template(self):
        good = values()
        self.assertEqual(metadata(good, "main")["version"], "2.1.0")
        for platform in PLATFORMS:
            for name, bad in ((placeholder("url", platform), url(platform).replace("Sakeliga/", "attacker/")),
                              (placeholder("url", platform), url(platform) + "/../x"),
                              (placeholder("sha256", platform), "0" * 63)):
                with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                    metadata({**good, name: bad}, "main")

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
    def test_formula_matches_template_on_both_branches(self):
        for base, tag in (("main", "mosaik-v2.1.0"), ("rehearsal", "rehearsal-v2.1.0-123-2")):
            self.assertEqual(check(base, tag=tag)["version"], "2.1.0")

    def test_render_equals_literal_substitution_and_extract_inverts_it(self):
        rendered = render(TEMPLATE.read_bytes(), values())
        self.assertEqual(rendered, formula())
        self.assertNotIn(b"{{", rendered)
        self.assertEqual(extract(rendered, TEMPLATE.read_bytes()), values())

    def test_template_has_no_runtime_dependency_and_installs_one_executable(self):
        template = TEMPLATE.read_text()
        for gone in ('depends_on "', "node@24", "/bin/sh", "libexec", ".mjs"):
            self.assertNotIn(gone, template)
        self.assertIn('bin.install "mosaik"\n', template)
        for name in patterns():
            self.assertEqual(template.count("{{" + name + "}}"), 1, name)

    def test_added_ruby_changed_install_or_newline_fails(self):
        original = formula()
        for changed in (original + b'system "echo unexpected"\n',
                        original.replace(b'bin.install "mosaik"', b'bin.install "mosaik"\n    system "bad"'),
                        original.replace(b"on_intel", b"on_arm", 1),
                        original.rstrip(b"\n"),
                        original.replace(b"\n", b"\r\n"),
                        original.replace(b"  license", b'  depends_on "node@24"\n  license'),
                        original.replace(b'      url "', b'      url "https://example.com/x.tar.gz"\n      url "', 1),
                        original + b'  sha256 "' + b"b" * 64 + b'"\n'):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "byte for byte"):
                verify_formula(changed, TEMPLATE.read_bytes(), "main")

    def test_repeated_placeholders_preserve_other_bytes_and_must_agree(self):
        names = [name for name in patterns() if name != "version"]
        template = (" ".join("{{" + name + "}}" for name in names)
                    + "\r\n{{version}} {{version}} {{sha256_linux_x64}}\n").encode()
        given = values()
        rendered = render(template, given)
        self.assertEqual(rendered, (" ".join(given[name] for name in names) + "\r\n2.1.0 2.1.0 "
                                    + given["sha256_linux_x64"] + "\n").encode())
        self.assertEqual(extract(rendered, template), given)
        with self.assertRaisesRegex(ValueError, "byte for byte"):
            extract(rendered.replace(b"2.1.0 2.1.0", b"2.1.0 2.1.1"), template)

    def test_template_without_version_line_takes_the_version_from_the_urls(self):
        template = TEMPLATE.read_bytes().replace(b'  version "{{version}}"\n', b"")
        self.assertNotIn(b"{{version}}", template)
        rendered = render(template, values())
        self.assertEqual(verify_formula(rendered, template, "main")["version"], "2.1.0")
        with self.assertRaisesRegex(ValueError, "byte for byte"):
            verify_formula(formula(), template, "main")

    def test_unknown_incomplete_missing_placeholders_and_unsafe_values_fail(self):
        complete = " ".join("{{" + name + "}}" for name in patterns() if name != "version")
        rendered = render(complete.encode(), values())
        for name in patterns():
            if name == "version":
                continue
            missing = complete.replace("{{" + name + "}}", "x").encode()
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, "missing required"):
                render(missing, values())
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, "missing required"):
                extract(rendered, missing)
        for extra in (" {{other}}", " {{", " {{version ", " {{url}}", " {{sha256}}", " {{URL_LINUX_X64}}"):
            template = (complete + extra).encode()
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "unknown or incomplete"):
                render(template, values())
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "unknown or incomplete"):
                extract(rendered, template)
        good = values()
        for name, bad in (("version", "2.1.0-rc.1"), ("version", "2.1.0\n"),
                          ("url_linux_x64", good["url_linux_x64"] + '"\nsystem "bad"'),
                          ("url_linux_x64", good["url_linux_arm64"]),
                          ("url_darwin_arm64", good["url_darwin_x64"]),
                          ("sha256_darwin_x64", "xyz"), ("sha256_linux_arm64", "a" * 64 + "\n")):
            with self.subTest(name=name, bad=bad), self.assertRaisesRegex(ValueError, f"invalid {name}"):
                render(TEMPLATE.read_bytes(), {**good, name: bad})
        for wrong in ({name: value for name, value in good.items() if name != "sha256_linux_x64"},
                      {**good, "url": good["url_linux_x64"]}):
            with self.subTest(names=sorted(wrong)), self.assertRaisesRegex(ValueError, "exactly"):
                render(TEMPLATE.read_bytes(), wrong)


class CommandLineTest(unittest.TestCase):
    def run_render(self, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Formula/mosaik.rb"
            result = subprocess.run([sys.executable, str(SCRIPTS / "render_formula.py"),
                                     "--template", str(TEMPLATE), "--output", str(output), *arguments],
                                    capture_output=True)
            return result.returncode, output.read_bytes() if output.exists() else None

    def test_release_options_render_what_verification_accepts(self):
        arguments = []
        for name, value in values().items():
            arguments += ["--" + name.replace("_", "-"), value]
        code, rendered = self.run_render(*arguments)
        self.assertEqual(code, 0)
        self.assertEqual(rendered, formula())

    def test_example_renders_every_platform_and_refuses_partial_input(self):
        code, rendered = self.run_render("--example")
        self.assertEqual(code, 0)
        self.assertEqual(rendered, render(TEMPLATE.read_bytes(), example_values()))
        for arguments in ((), ("--version", "2.1.0"), ("--example", "--version", "2.1.0")):
            code, rendered = self.run_render(*arguments)
            with self.subTest(arguments=arguments):
                self.assertNotEqual(code, 0)
                self.assertIsNone(rendered)


if __name__ == "__main__":
    unittest.main()
