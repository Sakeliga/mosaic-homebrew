"""Validate release metadata as data, before Homebrew evaluates the PR's Ruby."""

import argparse
import hashlib
import json
import re
from pathlib import Path

REPOSITORY = "Sakeliga/mosaic-homebrew"
WORKFLOW = "https://github.com/Sakeliga/mosaic-auth/.github/workflows/deploy.yml"
ISSUER = "https://token.actions.githubusercontent.com"
STABLE = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
PRERELEASE = r"(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?"


def metadata(formula, base):
    fields = {}
    for field in ("url", "version", "sha256"):
        matches = re.findall(r'^  ' + field + r' "([^"\r\n]+)"$', formula, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f"expected exactly one literal {field}")
        fields[field] = matches[0]
    version = fields["version"]
    if base not in ("main", "rehearsal"):
        raise ValueError("only main and rehearsal are release destinations")
    pattern = STABLE if base == "main" else STABLE + PRERELEASE
    if not re.fullmatch(pattern, version):
        raise ValueError(f"invalid {base} version")
    if not re.fullmatch(r"[0-9a-f]{64}", fields["sha256"]):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    asset = f"mosaik-{version}.tar.gz"
    prefix = f"https://github.com/{REPOSITORY}/releases/download/"
    if base == "main":
        tag = f"mosaik-v{version}"
        identity = f"{WORKFLOW}@refs/tags/v{version}"
        identity_flag = "--certificate-identity"
    else:
        match = re.fullmatch(
            re.escape(prefix) + r"(rehearsal-v" + re.escape(version)
            + r"-[1-9][0-9]*)/" + re.escape(asset), fields["url"]
        )
        if not match:
            raise ValueError("rehearsal URL must name this version's rehearsal release")
        tag = match[1]
        identity = "^" + re.escape(WORKFLOW) + r"@refs/heads/rehearsal/[A-Za-z0-9._/-]+$"
        identity_flag = "--certificate-identity-regexp"
    if fields["url"] != f"{prefix}{tag}/{asset}":
        raise ValueError("URL must name this repository's exact versioned release asset")
    return {**fields, "tag": tag, "asset": asset, "identity": identity,
            "identity_flag": identity_flag, "issuer": ISSUER}


def verify_digest(path, expected):
    digest = hashlib.sha256()
    with path.open("rb") as blob:
        for chunk in iter(lambda: blob.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        raise ValueError(f"sha256 mismatch: expected {expected}, got {actual}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formula", type=Path, default=Path("Formula/mosaik.rb"))
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    release = metadata(args.formula.read_text(), args.base)
    if args.archive:
        verify_digest(args.archive, release["sha256"])
    args.output.write_text(json.dumps(release) + "\n")


if __name__ == "__main__":
    main()
