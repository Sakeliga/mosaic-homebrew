"""The check names `main` requires are reported only by runs whose base is `main`.

Check runs attach to a commit, so a run for a pull request into another base
branch must never report a required name for the same head. The workflows are
read as text: every job-level `name:` is either a literal that is not a
required name, or the one expression form evaluated here for each base.
"""

import json
import re
import unittest
from pathlib import Path

GITHUB = Path(__file__).resolve().parents[1]
REQUIRED = {check["context"] for rule in json.loads((GITHUB / "rulesets/main-integrity.json").read_text())["rules"]
            if rule["type"] == "required_status_checks"
            for check in rule["parameters"]["required_status_checks"]}
BY_BASE = re.compile(r"\$\{\{ github\.base_ref == 'main' && '([a-z-]+)' \|\| '([a-z-]+)' \}\}")


def job_names(workflow):
    """Each job's `name:` value: the four-space-indented `name:` lines under `jobs:`."""
    text = (GITHUB / "workflows" / workflow).read_text()
    jobs = text[text.index("\njobs:\n"):]
    return re.findall(r"^    name: (.+)$", jobs, re.MULTILINE), len(re.findall(r"^  [a-z-]+:$", jobs, re.MULTILINE))


def name_for(value, base):
    match = BY_BASE.fullmatch(value)
    if match:
        return match[1] if base == "main" else match[2]
    if "base_ref" in value or "github." in value:
        raise AssertionError(f"job name depends on the event in an unreviewed form: {value}")
    return value


class WorkflowNamesTest(unittest.TestCase):
    def names(self, base):
        result = []
        for workflow in ("verify.yml", "homebrew.yml"):
            values, jobs = job_names(workflow)
            self.assertEqual(len(values), jobs, f"{workflow}: every job states its name")
            result += [name_for(value, base) for value in values]
        return result

    def test_required_names_are_the_two_this_tap_documents(self):
        self.assertEqual(REQUIRED, {"verify", "trusted-release"})

    def test_a_run_into_main_reports_each_required_name_once(self):
        names = self.names("main")
        for required in REQUIRED:
            self.assertEqual(names.count(required), 1, required)

    def test_a_run_into_any_other_base_reports_no_required_name(self):
        for base in ("rehearsal", "Main", "main2", "refs/heads/main", "", "propose/mosaik-v2.1.0"):
            names = self.names(base)
            with self.subTest(base=base):
                self.assertEqual(REQUIRED & set(names), set())
                self.assertIn("rehearsal-trusted-release", names)
                self.assertIn("rehearsal-verify", names)

    def test_no_literal_job_name_is_a_required_name(self):
        for workflow in ("verify.yml", "homebrew.yml"):
            for value in job_names(workflow)[0]:
                with self.subTest(workflow=workflow, name=value):
                    self.assertNotIn(value.strip("\"'"), REQUIRED)

    def test_only_the_reviewed_expression_form_is_accepted(self):
        for value in ("${{ github.base_ref != 'x' && 'verify' || 'other' }}",
                      "${{ github.head_ref }}", "${{ format('{0}', github.base_ref) }}"):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                name_for(value, "rehearsal")


if __name__ == "__main__":
    unittest.main()
