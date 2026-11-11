"""Render the release formula without evaluating Ruby or changing template bytes."""

import argparse
import re
from pathlib import Path

VERSION = r"[0-9]+\.[0-9]+\.[0-9]+"
URL = (r"https://github\.com/Sakeliga/mosaic-homebrew/releases/download/"
       r"(?:mosaik-v|rehearsal-v)[0-9A-Za-z.-]+/mosaik-[0-9.]+\.tar\.gz")


def render(template, version, url, sha256):
    for field, value, pattern in (("version", version, VERSION), ("url", url, URL),
                                  ("sha256", sha256, r"[0-9a-f]{64}")):
        if not re.fullmatch(pattern, value):
            raise ValueError(f"invalid {field}")
    for required in (b"{{url}}", b"{{sha256}}"):
        if required not in template:
            raise ValueError(f"missing required placeholder {required.decode()}")
    rendered = template
    for name, value in (("version", version), ("url", url), ("sha256", sha256)):
        rendered = rendered.replace(("{{" + name + "}}").encode(), value.encode())
    if b"{{" in rendered:
        raise ValueError("unknown or incomplete template placeholder")
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=Path("templates/mosaik.rb.tmpl"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rendered = render(args.template.read_bytes(), args.version, args.url, args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)


if __name__ == "__main__":
    main()
