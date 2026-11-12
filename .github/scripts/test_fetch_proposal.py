"""Reject event inputs that could fetch a different repository, ref or commit."""

import copy
import unittest

from fetch_proposal import REPOSITORY, event_refs


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


if __name__ == "__main__":
    unittest.main()
