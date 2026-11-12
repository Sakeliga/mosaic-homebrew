"""Fetch the event's exact PR head as bare Git data; never check it out."""

import argparse
import base64
import json
import os
import re
import subprocess
from pathlib import Path

REPOSITORY = "Sakeliga/mosaic-homebrew"


def event_refs(event):
    pr = event["pull_request"]
    number = event["number"]
    if type(number) is not int or number < 1:
        raise ValueError("invalid pull request number")
    if event["repository"]["full_name"] != REPOSITORY or pr["base"]["repo"]["full_name"] != REPOSITORY:
        raise ValueError("unexpected base repository")
    if pr["base"]["ref"] not in ("main", "rehearsal"):
        raise ValueError("unexpected base branch")
    for sha in (pr["base"]["sha"], pr["head"]["sha"]):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("invalid commit ID")
    return number, pr["base"]["sha"], pr["head"]["sha"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--base-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    number, base, head = event_refs(json.loads(args.event.read_text()))
    # A new directory prevents reuse of another run's configuration or Git objects.
    args.output.mkdir()
    subprocess.run(["git", "init", "--bare", "--quiet", str(args.output)], check=True)
    command = ["git", "-C", str(args.output), "-c", "gc.auto=0", "fetch", "--quiet", "--no-tags", "--depth=1"]
    subprocess.run(command + [str(args.base_checkout.resolve()), base], check=True)
    env = os.environ.copy()
    token = env.pop("GH_TOKEN")
    authorization = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
               GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {authorization}", GIT_TERMINAL_PROMPT="0")
    subprocess.run(command + [f"https://github.com/{REPOSITORY}.git",
                              f"refs/pull/{number}/head:refs/heads/proposal"], check=True, env=env)
    actual = subprocess.run(["git", "-C", str(args.output), "rev-parse", "refs/heads/proposal"],
                            check=True, capture_output=True, text=True).stdout.strip()
    if actual != head:
        raise ValueError("PR head changed since this event; rerun for the new head")


if __name__ == "__main__":
    main()
