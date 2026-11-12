"""Inspect PR Git objects using policy and a template from the trusted base."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from verify_release import verify_formula
from verify_tree import verify_tree

FORMULA = b"Formula/mosaik.rb"


def git(repository, *args):
    return subprocess.run(["git", "-C", str(repository), *args],
                          check=True, capture_output=True).stdout


def verify_proposal(repository, base_sha, head_sha, branch):
    for sha in (base_sha, head_sha):
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            raise ValueError("base and head must be full Git object IDs")
    if branch not in ("main", "rehearsal"):
        raise ValueError("only main and rehearsal are release destinations")
    present = verify_tree(repository, head_sha)
    changed = set(git(repository, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                      "--name-only", "-z", base_sha, head_sha, "--").split(b"\0")) - {b""}
    result = {"base_sha": base_sha, "head_sha": head_sha, "mode": "static"}
    if FORMULA not in changed:
        return result
    other = changed - {FORMULA}
    if other:
        paths = ", ".join(repr(path.decode("utf-8", errors="backslashreplace")) for path in sorted(other))
        raise ValueError(f"a formula change must be the only changed path; also changed: {paths}")
    if not present:
        raise ValueError("a release proposal cannot remove Formula/mosaik.rb")
    formula = git(repository, "show", f"{head_sha}:Formula/mosaik.rb")
    template = git(repository, "show", f"{base_sha}:templates/mosaik.rb.tmpl")
    release = verify_formula(formula, template, branch)
    return {**result, **release, "mode": "release"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    proposal = verify_proposal(args.repository, args.base_sha, args.head_sha, args.branch)
    args.output.write_text(json.dumps(proposal) + "\n")
    print(f"mode={proposal['mode']}")


if __name__ == "__main__":
    main()
