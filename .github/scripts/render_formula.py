"""Render the release formula without evaluating Ruby or changing template bytes."""

import argparse
import re
from pathlib import Path

# The platforms a release ships a binary for. This tuple is the only platform
# list in the scripts: placeholders, command-line options, URL rules and the
# download check all follow it. The template and the installation matrix in
# homebrew.yml name the same platforms and must change with it.
PLATFORMS = ("darwin-arm64", "darwin-x64", "linux-x64", "linux-arm64")

# Canonical only: each number is 0 or has no leading zero, so 2.010.0 cannot stand for 2.10.0.
NUMBER = r"(?:0|[1-9][0-9]*)"
VERSION = NUMBER + r"\." + NUMBER + r"\." + NUMBER
SHA256 = r"[0-9a-f]{64}"
RELEASES = "https://github.com/Sakeliga/mosaic-homebrew/releases/download/"


def placeholder(kind, platform):
    return f"{kind}_{platform.replace('-', '_')}"


def url_pattern(platform):
    return (re.escape(RELEASES) + r"(?:mosaik-v|rehearsal-v)[0-9A-Za-z.-]+/mosaik-[0-9.]+-"
            + re.escape(platform) + r"\.tar\.gz")


def patterns():
    """Every placeholder name with the full pattern its value must match."""
    fields = {"version": VERSION}
    for platform in PLATFORMS:
        fields[placeholder("url", platform)] = url_pattern(platform)
        fields[placeholder("sha256", platform)] = SHA256
    return fields


def required():
    return [name for name in patterns() if name != "version"]


def render(template, values):
    fields = patterns()
    if set(values) != set(fields):
        raise ValueError("values must name exactly: " + ", ".join(fields))
    for name, pattern in fields.items():
        if not re.fullmatch(pattern, values[name]):
            raise ValueError(f"invalid {name}")
    for name in required():
        if ("{{" + name + "}}").encode() not in template:
            raise ValueError("missing required placeholder {{" + name + "}}")
    rendered = template
    for name in fields:
        rendered = rendered.replace(("{{" + name + "}}").encode(), values[name].encode())
    if b"{{" in rendered:
        raise ValueError("unknown or incomplete template placeholder")
    return rendered


def example_values():
    """Well-formed values for style checks; they name no real release."""
    values = {"version": "0.0.0"}
    for platform in PLATFORMS:
        values[placeholder("url", platform)] = (
            f"{RELEASES}mosaik-v0.0.0/mosaik-0.0.0-{platform}.tar.gz")
        values[placeholder("sha256", platform)] = "0" * 64
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=Path("templates/mosaik.rb.tmpl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--example", action="store_true",
                        help="render placeholder values for style checks instead of a release")
    for name in patterns():
        parser.add_argument("--" + name.replace("_", "-"), dest=name)
    args = parser.parse_args()
    given = {name: getattr(args, name) for name in patterns()}
    if args.example:
        if any(value is not None for value in given.values()):
            parser.error("--example takes no release values")
        given = example_values()
    elif any(value is None for value in given.values()):
        parser.error("every release value is required: "
                     + ", ".join("--" + name.replace("_", "-") for name in given))
    rendered = render(args.template.read_bytes(), given)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)


if __name__ == "__main__":
    main()
