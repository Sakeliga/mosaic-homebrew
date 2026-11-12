"""Real Git-tree fixtures for alternate Homebrew entry points and file types."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from verify_tree import verify_tree


class TapTreeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--quiet")
        self.write("templates/mosaik.rb.tmpl")
        self.write(".github/workflows/verify.yml")
        for name in ("README.md", "SECURITY.md", "LICENSE", ".gitignore"):
            self.write(name)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True).stdout.decode().strip()

    def write(self, path):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture\n")

    def check(self):
        self.git("add", "--all")
        return verify_tree(self.root, self.git("write-tree"))

    def test_allowlisted_bootstrap_and_release(self):
        self.write(".github/scripts/check.py")
        (self.root / ".github/scripts/check.py").chmod(0o755)
        self.assertFalse(self.check())
        self.write("Formula/mosaik.rb")
        self.assertTrue(self.check())

    def test_nested_duplicate_formula_rejected(self):
        self.write("Formula/mosaik.rb")
        self.write("Formula/m/mosaik.rb")
        with self.assertRaisesRegex(ValueError, "outside tap allowlist"):
            self.check()

    def test_nested_only_formula_is_not_bootstrap(self):
        self.write("Formula/m/mosaik.rb")
        with self.assertRaisesRegex(ValueError, "outside tap allowlist"):
            self.check()

    def test_external_brew_command_rejected(self):
        self.write("cmd/brew-mosaik.rb")
        with self.assertRaisesRegex(ValueError, "outside tap allowlist"):
            self.check()

    def test_alias_rejected(self):
        self.write("Aliases/mosaik")
        with self.assertRaisesRegex(ValueError, "outside tap allowlist"):
            self.check()

    def test_symlinked_formula_rejected(self):
        (self.root / "Formula").mkdir()
        (self.root / "Formula/mosaik.rb").symlink_to("../templates/mosaik.rb.tmpl")
        with self.assertRaisesRegex(ValueError, "non-regular tree entry"):
            self.check()

    def test_symlink_inside_github_rejected(self):
        (self.root / ".github/linked").symlink_to("../templates", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "non-regular tree entry"):
            self.check()

    def test_submodule_inside_github_rejected(self):
        self.git("add", "--all")
        tree = self.git("write-tree")
        # A gitlink's object need not exist locally, just as with an uninitialized submodule.
        self.git("update-index", "--add", "--cacheinfo", f"160000,{tree},.github/vendor")
        with self.assertRaisesRegex(ValueError, "non-regular tree entry"):
            verify_tree(self.root, self.git("write-tree"))

    def test_other_tap_entry_points_rejected(self):
        for path in ("Casks/mosaik.rb", "HomebrewFormula/mosaik.rb", "mosaik.rb",
                     "formula_renames.json", "tap_migrations.json", "unexpected.txt"):
            with self.subTest(path=path):
                self.write(path)
                with self.assertRaisesRegex(ValueError, "outside tap allowlist"):
                    self.check()
                (self.root / path).unlink()


if __name__ == "__main__":
    unittest.main()
