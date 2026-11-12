"""Which check names each workflow file can report, and for which base branch.

`main` requires two check names. GitHub attaches a check run to a commit, not
to a pull request, so a run for a pull request into another base must not
report either name for the same head. Two things enforce that in the
workflows, and this file checks both in every file under `.github/workflows/`:

1. The job's name is an expression on the base branch. GitHub compares strings
   in expressions without regard to case, so `Main` also selects the required
   name. The model here does the same.
2. The job's first step therefore fails unless the base is exactly `main`.
   The step's script is run here, in bash, for each base.

The reader below handles the subset of YAML these workflows use and refuses
anything else at the levels it reads (job ids, job-level `name`, the first
step), so syntax it does not understand is a failure, not a pass. It cannot
show what a workflow file added by a pull request reports on GitHub; see
"Known limit" in `.github/settings.md`.
"""

import json
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

GITHUB = Path(__file__).resolve().parents[1]
WORKFLOWS = GITHUB / "workflows"
REQUIRED = {check["context"] for rule in json.loads((GITHUB / "rulesets/main-integrity.json").read_text())["rules"]
            if rule["type"] == "required_status_checks"
            for check in rule["parameters"]["required_status_checks"]}
# The only workflow files that may report a required name, and which one.
INTENDED = {"verify.yml": "trusted-release", "homebrew.yml": "verify"}
TRIGGER = {"verify.yml": "on:\n  pull_request_target:\n    branches: [main, rehearsal]\n"
                         "    types: [opened, synchronize, reopened, edited]\n",
           "homebrew.yml": "on:\n  pull_request:\n    branches: [main, rehearsal]\n"}
BY_BASE = re.compile(r"\$\{\{ github\.base_ref == 'main' && '([a-z-]+)' \|\| '([a-z-]+)' \}\}")
GUARD = """\
- name: Refuse a required check name for any base but main
  env:
    BASE_REF: ${{ github.base_ref }}
    REQUIRED_NAME: ${{ github.base_ref == 'main' }}
  run: |
    # Expressions compare without regard to case, so `Main` also gets the
    # required name above. The shell compares exactly.
    if [[ "$REQUIRED_NAME" == "true" && "$BASE_REF" != "main" ]]; then
      echo "Base '$BASE_REF' is not main; this run may not report a check that main requires." >&2
      exit 1
    fi
"""
KEY = re.compile(r"""(?:"([^"\\]*)"|'([^']*)'|([A-Za-z0-9_.-]+))[ ]*:(?:[ ]+(.*))?$""")


class Unparsed(ValueError):
    """The workflow uses YAML this reader does not handle where a check name is decided."""


def entry(content):
    """Split one `key: value` line; the key may be quoted."""
    match = KEY.match(content)
    if not match:
        raise Unparsed(f"not a plain mapping entry: {content!r}")
    key = next(group for group in match.groups()[:3] if group is not None)
    return key, match[4]


def scalar(rest):
    """A one-line scalar value with any trailing comment removed; None when there is no value."""
    if rest is None or rest.startswith("#"):
        return None
    if rest[0] == '"':
        match = re.fullmatch(r'"([^"\\]*)"[ ]*(?:[ ]#.*)?', rest)
    elif rest[0] == "'":
        match = re.fullmatch(r"'([^']*)'[ ]*(?:[ ]#.*)?", rest)
    elif rest[0] in "|>&*!{[%@`,?-":
        raise Unparsed(f"not a one-line scalar: {rest!r}")
    else:
        match = re.fullmatch(r"(.*?)(?:[ ]+#.*)?", rest)
    if not match:
        raise Unparsed(f"not a one-line scalar: {rest!r}")
    return match[1].rstrip()


def read_workflow(text):
    """The trigger block, and each job's id, stated name and first step."""
    lines, source = [], text.splitlines()
    for number, raw in enumerate(source):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if raw[indent] == "\t" or raw.startswith(("---", "...", "%")):
            raise Unparsed(f"tabs or document markers: {raw!r}")
        lines.append((indent, raw[indent:], raw, number))
    top = [index for index, line in enumerate(lines) if line[0] == 0]
    blocks = {}
    for position, index in enumerate(top):
        key, rest = entry(lines[index][1])
        if key in blocks:
            raise Unparsed(f"repeated top-level key {key!r}")
        end = top[position + 1] if position + 1 < len(top) else len(lines)
        blocks[key] = (rest, lines[index:end])
    if "jobs" not in blocks or scalar(blocks["jobs"][0]) is not None:
        raise Unparsed("jobs must be a block mapping")
    trigger = "".join(line[2] + "\n" for line in blocks.get("on", (None, []))[1])
    body = blocks["jobs"][1][1:]
    if not body:
        raise Unparsed("no jobs")
    job_indent = body[0][0]
    starts = [index for index, line in enumerate(body) if line[0] == job_indent]
    if any(line[0] < job_indent for line in body):
        raise Unparsed("inconsistent indentation under jobs")
    jobs, seen = [], set()
    for position, index in enumerate(starts):
        job_id, rest = entry(body[index][1])
        if scalar(rest) is not None or job_id in seen:
            raise Unparsed(f"job {job_id!r} is repeated or not a block mapping")
        seen.add(job_id)
        end = starts[position + 1] if position + 1 < len(starts) else len(body)
        jobs.append(read_job(job_id, body[index + 1:end], source))
    return trigger, jobs


def read_job(job_id, body, source):
    job = {"id": job_id, "name": None, "first_step": None}
    if not body:
        raise Unparsed(f"job {job_id!r} is empty")
    key_indent = body[0][0]
    keys = set()
    for index, (indent, content, _, _) in enumerate(body):
        if indent < key_indent:
            raise Unparsed(f"inconsistent indentation in job {job_id!r}")
        if indent > key_indent:
            continue
        key, rest = entry(content)
        if key in keys:
            raise Unparsed(f"job {job_id!r} repeats {key!r}")
        keys.add(key)
        following = body[index + 1:]
        nested = [line for line in following[:1] if line[0] > key_indent]
        if key == "name":
            job["name"] = scalar(rest)
            if job["name"] is None or nested:
                raise Unparsed(f"job {job_id!r}: name is not a one-line scalar")
        elif key == "steps":
            if scalar(rest) is not None or not nested or not nested[0][1].startswith("- "):
                raise Unparsed(f"job {job_id!r}: steps is not a block sequence")
            step_indent = nested[0][0]
            step = [following[0]]
            for line in following[1:]:
                if line[0] <= step_indent:
                    break
                step.append(line)
            # Every source line of the step, so the comments inside its script count too.
            job["first_step"] = "".join(raw[step_indent:] + "\n"
                                        for raw in source[step[0][3]:step[-1][3] + 1])
    return job


def reportable(name, required):
    """The required names a job with this literal or templated name could report."""
    if "${{" not in name:
        return {check for check in required if check.lower() == name.lower()}
    pattern = ".*".join(re.escape(part) for part in re.split(r"\$\{\{.*?\}\}", name))
    return {check for check in required if re.fullmatch(pattern, check, re.IGNORECASE | re.DOTALL)}


def name_for(value, base):
    """GitHub's evaluation of the reviewed name expression: `==` ignores case."""
    match = BY_BASE.fullmatch(value)
    return match[1] if base.lower() == "main" else match[2]


def problems(workflows=WORKFLOWS, required=frozenset(REQUIRED)):
    """Every way a workflow file in this directory could report a required name it should not."""
    found = []
    reporters = {name: 0 for name in INTENDED}
    files = sorted(path for path in workflows.iterdir() if path.suffix in (".yml", ".yaml"))
    for path in files:
        try:
            trigger, jobs = read_workflow(path.read_text())
        except Unparsed as error:
            found.append(f"{path.name}: {error}")
            continue
        if path.name in INTENDED and trigger != TRIGGER[path.name]:
            found.append(f"{path.name}: the trigger is not the reviewed one")
        for job in jobs:
            name = job["id"] if job["name"] is None else job["name"]
            match = BY_BASE.fullmatch(name)
            if not match:
                for check in sorted(reportable(name, required)):
                    found.append(f"{path.name}: job {job['id']!r} could report {check!r} for every base")
                continue
            if match[2] in required:
                found.append(f"{path.name}: job {job['id']!r} reports {match[2]!r} for other bases")
            if match[1] not in required:
                continue
            if INTENDED.get(path.name) != match[1]:
                found.append(f"{path.name}: job {job['id']!r} may not report {match[1]!r}")
                continue
            reporters[path.name] += 1
            if job["first_step"] != GUARD:
                found.append(f"{path.name}: job {job['id']!r} does not start with the base guard")
    for name, count in reporters.items():
        if count != 1:
            found.append(f"{name}: {count} jobs report {INTENDED[name]!r}; expected one")
    return found


def guard_exit(base, required_name):
    """Run the guard step's script as the runner would, with the values in the environment."""
    script = textwrap.dedent(GUARD.split("  run: |\n", 1)[1])
    return subprocess.run(["bash", "-e", "-c", script], capture_output=True,
                          env={"PATH": "/usr/bin:/bin", "BASE_REF": base,
                               "REQUIRED_NAME": "true" if required_name else "false"}).returncode


class WorkflowNamesTest(unittest.TestCase):
    def names(self):
        return {name: next(job["name"] for job in read_workflow((WORKFLOWS / name).read_text())[1]
                           if job["name"] and BY_BASE.fullmatch(job["name"]))
                for name in INTENDED}

    def test_required_names_are_the_two_this_tap_documents(self):
        self.assertEqual(REQUIRED, {"verify", "trusted-release"})
        self.assertEqual(set(INTENDED.values()), REQUIRED)

    def test_the_committed_workflows_have_no_problem(self):
        self.assertEqual(problems(), [])

    def test_a_run_into_main_reports_the_required_name_and_passes_the_guard(self):
        for workflow, value in self.names().items():
            self.assertEqual(name_for(value, "main"), INTENDED[workflow])
        self.assertEqual(guard_exit("main", True), 0)

    def test_a_run_into_another_base_reports_another_name_and_passes_the_guard(self):
        for base in ("rehearsal", "main2", "mai", "refs/heads/main", "", "propose/mosaik-v2.1.0"):
            for workflow, value in self.names().items():
                with self.subTest(base=base, workflow=workflow):
                    self.assertEqual(name_for(value, base), "rehearsal-" + INTENDED[workflow])
            self.assertEqual(guard_exit(base, False), 0)

    def test_a_base_that_differs_from_main_only_in_case_gets_the_name_and_is_stopped(self):
        for base in ("Main", "MAIN", "mAin", "maiN"):
            for workflow, value in self.names().items():
                with self.subTest(base=base, workflow=workflow):
                    # This is why the name expression alone is not the control.
                    self.assertEqual(name_for(value, base), INTENDED[workflow])
            with self.subTest(base=base):
                self.assertNotEqual(guard_exit(base, True), 0)

    def test_the_guard_stops_every_base_but_main_once_the_required_name_is_chosen(self):
        for base in ("rehearsal", "main ", " main", "main\n", "mai*", "*", "", "refs/heads/main"):
            with self.subTest(base=base):
                self.assertNotEqual(guard_exit(base, True), 0)

    def test_reader_handles_quoting_comments_and_refuses_what_it_cannot_read(self):
        text = ('on: push\n"jobs":\n  "a" :   # comment\n    name: \'x # y\'   # comment\n'
                "    steps:\n      - run: one\n        shell: bash\n      - run: two\n"
                "  b: # id is the name\n    uses: ./x.yml\n")
        self.assertEqual(read_workflow(text)[1], [
            {"id": "a", "name": "x # y", "first_step": "- run: one\n  shell: bash\n"},
            {"id": "b", "name": None, "first_step": None}])
        self.assertEqual(scalar("verify # summary"), "verify")
        self.assertEqual(scalar(' verify'.strip()), "verify")
        for unreadable in ("on: push\njobs: {a: {}}\n", "on: push\njobs:\n  a:\n    name: >-\n      verify\n",
                           "on: push\njobs:\n  a:\n    name: x\n      y\n", "on: push\njobs:\n  a: &x\n    name: x\n",
                           "on: push\njobs:\n  a:\n    name: x\n    name: y\n", "on: push\njobs:\n  ? a\n  : {}\n",
                           "on: push\njobs:\n  a:\n    <<: *x\n", "on: push\njobs:\n  a:\n\tname: x\n",
                           "on: push\n---\njobs:\n  a:\n    name: x\n", "on: push\n"):
            with self.subTest(text=unreadable), self.assertRaises(Unparsed):
                read_workflow(unreadable)


OLD = {name: f"    name: ${{{{ github.base_ref == 'main' && '{check}' || 'rehearsal-{check}' }}}}"
       for name, check in INTENDED.items()}
EXTRA = "\n  {id}\n    runs-on: ubuntu-latest\n{name}    steps:\n      - run: 'true'\n"
SPOOF = ("name: Spoof\non:\n  pull_request:\npermissions: {}\njobs:\n  trusted-release:\n"
         "    name: trusted-release\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n")
FIRST_GUARD_LINE = "      - name: Refuse a required check name for any base but main\n"

# Each entry: file to change, text to find ("" appends; None writes a new file), replacement.
MUTATIONS = {
    "literal trusted-release": ("verify.yml", OLD["verify.yml"], "    name: trusted-release"),
    "literal verify": ("homebrew.yml", OLD["homebrew.yml"], "    name: verify"),
    "inverted expression": ("verify.yml", OLD["verify.yml"], OLD["verify.yml"].replace("==", "!=")),
    "nameless job whose id is verify": ("verify.yml", "", EXTRA.format(id="verify:", name="")),
    "nameless job id with a trailing comment": ("verify.yml", "", EXTRA.format(id="verify: # spoof", name="")),
    "nameless quoted job id": ("verify.yml", "", EXTRA.format(id='"verify":', name="")),
    "nameless single-quoted job id": ("homebrew.yml", "", EXTRA.format(id="'trusted-release' :", name="")),
    "name with two spaces": ("homebrew.yml", OLD["homebrew.yml"], "    name:  verify"),
    "name with a trailing comment": ("homebrew.yml", OLD["homebrew.yml"], "    name: verify # summary"),
    "quoted name": ("homebrew.yml", OLD["homebrew.yml"], '    name: "verify"'),
    "name differing in case": ("homebrew.yml", OLD["homebrew.yml"], "    name: Verify"),
    "name from a matrix value": ("verify.yml", OLD["verify.yml"],
                                 "    name: ${{ matrix.n }}\n    strategy:\n      matrix:\n        n: [trusted-release]"),
    "constant expression": ("verify.yml", OLD["verify.yml"], "    name: ${{ 'trusted-release' }}"),
    "name from a repository variable": ("verify.yml", OLD["verify.yml"], "    name: ${{ vars.N }}"),
    "templated name that can spell a required one": ("homebrew.yml", "", EXTRA.format(
        id="other:", name="    name: ver${{ matrix.n }}\n")),
    "third workflow file": ("spoof.yml", None, SPOOF),
    "third workflow file with the reviewed expression": ("spoof.yml", None, SPOOF.replace(
        "    name: trusted-release", OLD["verify.yml"])),
    "block-scalar name": ("homebrew.yml", OLD["homebrew.yml"], "    name: >-\n      verify"),
    "trigger widened to every base": ("verify.yml", "    branches: [main, rehearsal]\n", ""),
    "trigger widened in the unprivileged workflow": ("homebrew.yml", "    branches: [main, rehearsal]\n", ""),
    "second file extension, nameless job": ("extra.yaml", None,
                                            "on: pull_request\njobs:\n  verify:\n    runs-on: ubuntu-latest\n"
                                            "    steps:\n      - run: 'true'\n"),
    "other base given a required name": ("verify.yml", "'rehearsal-trusted-release'", "'verify'"),
    "required name swapped between files": ("homebrew.yml", OLD["homebrew.yml"], OLD["verify.yml"]),
    "guard removed": ("verify.yml", FIRST_GUARD_LINE, "      - name: Something else\n"),
    "guard no longer first": ("homebrew.yml", FIRST_GUARD_LINE, "      - run: 'true'\n" + FIRST_GUARD_LINE),
    "guard compares the other way": ("verify.yml", '"$BASE_REF" != "main"', '"$BASE_REF" == "main"'),
    "guard value interpolated into the script": ("verify.yml", '"$BASE_REF" != "main"',
                                                 '"${{ github.base_ref }}" != "main"'),
    "guard made to pass": ("verify.yml", "            exit 1\n", "            exit 0\n"),
    "second job reporting the required name": ("verify.yml", "", EXTRA.format(
        id="again:", name=OLD["verify.yml"] + "\n")),
}


class MutationTest(unittest.TestCase):
    """Each change that would let a job report a required name wrongly must be found."""

    def test_every_mutation_is_found(self):
        for label, (name, old, new) in MUTATIONS.items():
            with self.subTest(mutation=label), tempfile.TemporaryDirectory() as directory:
                workflows = Path(directory) / "workflows"
                shutil.copytree(WORKFLOWS, workflows)
                path = workflows / name
                if old is None:
                    path.write_text(new)
                elif old == "":
                    path.write_text(path.read_text() + new)
                else:
                    text = path.read_text()
                    self.assertEqual(text.count(old), 1, f"mutation does not apply: {old!r}")
                    path.write_text(text.replace(old, new))
                self.assertNotEqual(problems(workflows), [], label)

    def test_an_unrelated_workflow_file_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            workflows = Path(directory) / "workflows"
            shutil.copytree(WORKFLOWS, workflows)
            (workflows / "lint.yml").write_text(
                "on: push\njobs:\n  lint:\n    name: Lint (${{ matrix.os }})\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: 'true'\n")
            self.assertEqual(problems(workflows), [])


if __name__ == "__main__":
    unittest.main()
