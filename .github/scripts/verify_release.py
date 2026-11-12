"""Validate release metadata as data, before Homebrew evaluates the PR's Ruby."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from render_formula import PLATFORMS, RELEASES, patterns, placeholder, render, required

WORKFLOW = "https://github.com/Sakeliga/mosaic-auth/.github/workflows/deploy.yml"
ISSUER = "https://token.actions.githubusercontent.com"
STABLE = r"[0-9]+\.[0-9]+\.[0-9]+"
MISMATCH = "formula must exactly match the rendered template, byte for byte"


def extract(formula, template):
    """Read each placeholder's value out of a formula that is the template rendered.

    The template becomes one anchored pattern: its own bytes, literally, with a
    placeholder's value pattern wherever that placeholder stands. A formula that
    differs from the template anywhere else does not match.
    """
    fields = patterns()
    pieces = re.split(rb"\{\{([a-z0-9_]+)\}\}", template)
    pattern, seen = b"", set()
    for index, piece in enumerate(pieces):
        if index % 2 == 0:
            if b"{{" in piece:
                raise ValueError("unknown or incomplete template placeholder")
            pattern += re.escape(piece)
            continue
        name = piece.decode()
        if name not in fields:
            raise ValueError("unknown or incomplete template placeholder")
        if name in seen:
            pattern += b"(?P=" + piece + b")"
        else:
            pattern += b"(?P<" + piece + b">" + fields[name].encode() + b")"
            seen.add(name)
    for name in required():
        if name not in seen:
            raise ValueError("missing required placeholder {{" + name + "}}")
    match = re.fullmatch(pattern, formula)
    if not match:
        raise ValueError(MISMATCH)
    return {name: value.decode() for name, value in match.groupdict().items()}


def metadata(values, base):
    """Apply the branch's release policy to every platform's URL and hash."""
    if base not in ("main", "rehearsal"):
        raise ValueError("only main and rehearsal are release destinations")
    assets, tags, versions = [], set(), set()
    for platform in PLATFORMS:
        url = values[placeholder("url", platform)]
        sha256 = values[placeholder("sha256", platform)]
        match = re.fullmatch(re.escape(RELEASES) + r"([^/]+)/(mosaik-(" + STABLE + r")-"
                             + re.escape(platform) + r"\.tar\.gz)", url)
        if not match:
            raise ValueError(f"{platform}: URL must name this repository's release asset "
                             f"mosaik-X.Y.Z-{platform}.tar.gz")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError(f"{platform}: sha256 must be 64 lowercase hexadecimal characters")
        tags.add(match[1])
        versions.add(match[3])
        assets.append({"platform": platform, "asset": match[2], "url": url, "sha256": sha256})
    if len(versions) != 1:
        raise ValueError("every platform's URL must name the same version")
    if len(tags) != 1:
        raise ValueError("every platform's URL must name the same release tag")
    version, tag = versions.pop(), tags.pop()
    if values.get("version", version) != version:
        raise ValueError("the formula's version must equal the version in its URLs")
    if base == "main":
        if tag != f"mosaik-v{version}":
            raise ValueError("main accepts only this version's mosaik-vX.Y.Z release")
        identity = f"{WORKFLOW}@refs/tags/v{version}"
        identity_flag = "--certificate-identity"
    else:
        if not re.fullmatch(r"rehearsal-v" + re.escape(version) + r"-[1-9][0-9]*-[1-9][0-9]*", tag):
            raise ValueError("rehearsal URLs must name this version's rehearsal release")
        identity = "^" + re.escape(WORKFLOW) + r"@refs/heads/rehearsal/[A-Za-z0-9._/-]+$"
        identity_flag = "--certificate-identity-regexp"
    return {"version": version, "tag": tag, "assets": assets, "identity": identity,
            "identity_flag": identity_flag, "issuer": ISSUER}


def verify_formula(formula, template, base):
    values = extract(formula, template)
    release = metadata(values, base)
    if formula != render(template, {**values, "version": release["version"]}):
        raise ValueError(MISMATCH)
    return release


def verify_digest(path, expected):
    digest = hashlib.sha256()
    with path.open("rb") as blob:
        for chunk in iter(lambda: blob.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        raise ValueError(f"{path.name}: sha256 mismatch: expected {expected}, got {actual}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formula", type=Path, default=Path("Formula/mosaik.rb"))
    parser.add_argument("--template", type=Path, default=Path("templates/mosaik.rb.tmpl"))
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release = verify_formula(args.formula.read_bytes(), args.template.read_bytes(), args.base)
    args.output.write_text(json.dumps(release) + "\n")


if __name__ == "__main__":
    main()
