"""Real Git snapshots exercise the base/head trust boundary without running PR code."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from render_formula import PLATFORMS, placeholder, render
from test_verify_release import values
from verify_proposal import verify_proposal

TEMPLATE = Path(__file__).resolve().parents[2] / "templates/mosaik.rb.tmpl"

# Release 2.0.0 as it stands on `main`: rendered from the template that came
# before the per-platform one. It stays there until a later release replaces it.
FORMULA_2_0_0 = b'''class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.0.0/mosaik-2.0.0.tar.gz"
  sha256 "0450b2db79d12eeb5048c3ed568594dfc5a09b7fdc3532f78d61a56f99bd011b"
  license :cannot_represent

  depends_on "node@24"

  def install
    libexec.install "mosaik.mjs"
    pkgshare.install "guide.md"
    prefix.install "LICENSE"
    (bin/"mosaik").write <<~SH
      #!/bin/sh
      exec "#{formula_opt_bin("node@24")}/node" "#{libexec}/mosaik.mjs" "$@"
    SH
  end

  test do
    assert_equal version.to_s, shell_output("#{bin}/mosaik --version").strip
  end
end
'''


class ProposalTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--quiet")
        self.write("templates/mosaik.rb.tmpl", TEMPLATE.read_bytes())
        self.write(".github/scripts/verify_release.py", b"base checker\n")
        self.write(".github/workflows/verify.yml", b"base workflow\n")
        self.base = self.snapshot()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True).stdout.decode().strip()

    def write(self, path, contents):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    def snapshot(self):
        self.git("add", "--all")
        return self.git("write-tree")

    def formula(self, template=None, **changed):
        self.write("Formula/mosaik.rb", render(template or TEMPLATE.read_bytes(), {**values(), **changed}))

    def check(self):
        return verify_proposal(self.root, self.base, self.snapshot(), "main")

    def test_formula_only_uses_base_template(self):
        self.formula()
        proposal = self.check()
        self.assertEqual(proposal["mode"], "release")
        self.assertEqual([asset["platform"] for asset in proposal["assets"]], list(PLATFORMS))
        self.assertEqual(proposal["tag"], "mosaik-v2.1.0")

    def test_one_platform_changed_in_a_merged_formula_is_a_release(self):
        self.formula()
        self.base = self.snapshot()
        name = placeholder("sha256", PLATFORMS[-1])
        self.formula(**{name: "f" * 64})
        proposal = self.check()
        self.assertEqual(proposal["mode"], "release")
        self.assertEqual(proposal["assets"][-1]["sha256"], "f" * 64)

    def test_one_platform_outside_the_release_fails(self):
        for platform in PLATFORMS:
            name = placeholder("url", platform)
            other = values("2.0.9", "mosaik-v2.0.9")[name]
            self.formula(**{name: other})
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, "same version"):
                self.check()

    def test_untouched_old_formula_does_not_block_other_changes(self):
        # The state of `main` between the template change and the next release:
        # the new template beside a formula rendered from the old one.
        self.write("Formula/mosaik.rb", FORMULA_2_0_0)
        self.base = self.snapshot()
        self.assertEqual(self.check()["mode"], "static")
        for path in ("README.md", "templates/mosaik.rb.tmpl", ".github/scripts/verify_release.py"):
            self.write(path, b"changed in a later pull request\n")
            with self.subTest(path=path):
                self.assertEqual(self.check()["mode"], "static")

    def test_old_formula_is_replaced_only_by_the_new_template_rendered(self):
        self.write("Formula/mosaik.rb", FORMULA_2_0_0)
        self.base = self.snapshot()
        self.write("Formula/mosaik.rb", FORMULA_2_0_0.replace(b"0450b2db", b"0450b2dc"))
        with self.assertRaisesRegex(ValueError, "byte for byte"):
            self.check()
        self.formula()
        self.assertEqual(self.check()["mode"], "release")

    def test_template_change_beside_the_old_formula_is_static(self):
        # This pull request's own shape: the base holds the old template and its formula.
        self.write("templates/mosaik.rb.tmpl", b"the template before this change\n")
        self.write("Formula/mosaik.rb", FORMULA_2_0_0)
        self.base = self.snapshot()
        self.write("templates/mosaik.rb.tmpl", TEMPLATE.read_bytes())
        self.write(".github/scripts/verify_release.py", b"changed checker\n")
        self.assertEqual(self.check()["mode"], "static")

    def test_formula_plus_template_fails(self):
        changed = TEMPLATE.read_bytes().replace(b'bin.install "mosaik"', b'bin.install "mosaik" => "other"')
        self.assertNotEqual(changed, TEMPLATE.read_bytes())
        self.write("templates/mosaik.rb.tmpl", changed)
        self.formula(changed)
        with self.assertRaisesRegex(ValueError, "also changed: 'templates/mosaik.rb.tmpl'"):
            self.check()

    def test_formula_plus_script_fails(self):
        self.formula()
        self.write(".github/scripts/verify_release.py", b"raise SystemExit(0)\n")
        with self.assertRaisesRegex(ValueError, "also changed: '.github/scripts/verify_release.py'"):
            self.check()

    def test_formula_plus_workflow_fails(self):
        self.formula()
        self.write(".github/workflows/verify.yml", b"changed workflow\n")
        with self.assertRaisesRegex(ValueError, "also changed: '.github/workflows/verify.yml'"):
            self.check()

    def test_template_only_is_static_even_with_existing_formula(self):
        self.formula()
        self.base = self.snapshot()
        self.write("templates/mosaik.rb.tmpl", TEMPLATE.read_bytes() + b"# next release template\n")
        self.assertEqual(self.check()["mode"], "static")

    def test_template_only_bootstrap_is_static(self):
        self.write("templates/mosaik.rb.tmpl", TEMPLATE.read_bytes() + b"# reviewed separately\n")
        self.assertEqual(self.check()["mode"], "static")

    def test_formula_injection_fails_against_base_template(self):
        self.formula(TEMPLATE.read_bytes() + b'system "echo unexpected"\n')
        with self.assertRaisesRegex(ValueError, "byte for byte"):
            self.check()

    def test_formula_removal_rejected(self):
        self.formula()
        self.base = self.snapshot()
        (self.root / "Formula/mosaik.rb").unlink()
        with self.assertRaisesRegex(ValueError, "cannot remove"):
            self.check()

    def test_disallowed_tree_rejected_even_without_formula_change(self):
        self.write("cmd/brew-mosaik", b"bad\n")
        with self.assertRaisesRegex(ValueError, "outside tap allowlist"):
            self.check()


if __name__ == "__main__":
    unittest.main()
