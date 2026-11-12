"""Real Git snapshots exercise the base/head trust boundary without running PR code."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from render_formula import render
from verify_proposal import verify_proposal

TEMPLATE = Path(__file__).resolve().parents[2] / "templates/mosaik.rb.tmpl"
URL = "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.0.0/mosaik-2.0.0.tar.gz"


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

    def formula(self, template=None):
        self.write("Formula/mosaik.rb", render(template or TEMPLATE.read_bytes(), "2.0.0", URL, "a" * 64))

    def check(self):
        return verify_proposal(self.root, self.base, self.snapshot(), "main")

    def test_formula_only_uses_base_template(self):
        self.formula()
        self.assertEqual(self.check()["mode"], "release")

    def test_formula_plus_template_fails(self):
        changed = TEMPLATE.read_bytes().replace(b'exec ', b'echo ')
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
