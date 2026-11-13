"""Reject event inputs that could fetch a different repository, ref or commit."""

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from fetch_proposal import REPOSITORY, event_refs, trusted_base


class EventRefsTest(unittest.TestCase):
    def setUp(self):
        self.event = {
            "number": 123,
            "repository": {"full_name": REPOSITORY},
            "pull_request": {
                "base": {"ref": "main", "sha": "a" * 40, "repo": {"full_name": REPOSITORY}},
                "head": {"sha": "b" * 40},
            },
        }

    def test_event_binds_number_base_and_head(self):
        self.assertEqual(event_refs(self.event), (123, "a" * 40, "b" * 40))
        self.event["pull_request"]["base"]["ref"] = "rehearsal"
        self.assertEqual(event_refs(self.event), (123, "a" * 40, "b" * 40))

    def test_rejects_other_repository_or_branch(self):
        for target in ("repository", "base_repository", "branch"):
            event = copy.deepcopy(self.event)
            if target == "repository":
                event["repository"]["full_name"] = "attacker/tap"
            elif target == "base_repository":
                event["pull_request"]["base"]["repo"]["full_name"] = "attacker/tap"
            else:
                event["pull_request"]["base"]["ref"] = "unreviewed"
            with self.subTest(target=target), self.assertRaises(ValueError):
                event_refs(event)

    def test_base_branch_name_is_compared_exactly(self):
        for ref in ("Main", "MAIN", "main ", "refs/heads/main", "Rehearsal", "main\n", ""):
            self.event["pull_request"]["base"]["ref"] = ref
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "unexpected base branch"):
                event_refs(self.event)

    def test_rejects_refs_and_malformed_numbers(self):
        for number in (0, -1, True, "123", "123/head:refs/heads/other"):
            self.event["number"] = number
            with self.subTest(number=number), self.assertRaises(ValueError):
                event_refs(self.event)
        self.event["number"] = 123
        for side in ("base", "head"):
            for sha in ("main", "--upload-pack=bad", "a" * 39, "a" * 40 + "\n"):
                event = copy.deepcopy(self.event)
                event["pull_request"][side]["sha"] = sha
                with self.subTest(side=side, sha=sha), self.assertRaises(ValueError):
                    event_refs(event)


class TrustedBaseTest(unittest.TestCase):
    """Which commit's scripts judge a pull request, on real Git history."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--quiet", "--initial-branch=main")
        self.older = self.commit("first")
        self.tip = self.commit("second")
        self.git("checkout", "--quiet", "-b", "other", self.older)
        self.elsewhere = self.commit("scripts that accept anything")
        self.git("checkout", "--quiet", "main")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.com",
                               "-c", "commit.gpgsign=false", *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git("commit", "--quiet", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def test_main_is_judged_by_its_own_tip(self):
        self.assertEqual(trusted_base(self.root, "main", self.tip), self.tip)
        self.assertEqual(trusted_base(self.root, "main", self.older), self.tip)

    def test_main_refuses_a_base_commit_that_is_not_on_main(self):
        for base in (self.elsewhere, "c" * 40):
            with self.subTest(base=base), self.assertRaisesRegex(ValueError, "not a commit of main; update"):
                trusted_base(self.root, "main", base)

    def test_rehearsal_is_judged_by_the_events_base_commit_only(self):
        self.git("checkout", "--quiet", "other")
        self.assertEqual(trusted_base(self.root, "rehearsal", self.elsewhere), self.elsewhere)
        with self.assertRaisesRegex(ValueError, "not the event's base commit"):
            trusted_base(self.root, "rehearsal", self.older)

    def test_other_branch_names_and_empty_checkouts_are_refused(self):
        for branch in ("Main", "other", ""):
            with self.subTest(branch=branch), self.assertRaisesRegex(ValueError, "unexpected base branch"):
                trusted_base(self.root, branch, self.tip)
        with tempfile.TemporaryDirectory() as empty:
            subprocess.run(["git", "init", "--quiet", empty], check=True)
            with self.assertRaisesRegex(ValueError, "no commit"):
                trusted_base(Path(empty), "main", self.tip)


if __name__ == "__main__":
    unittest.main()
