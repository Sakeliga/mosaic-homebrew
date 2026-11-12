"""Allow only the reviewed tap layout; choose release mode from its Git tree."""

import argparse
import subprocess
from pathlib import Path

FILES = {
    b"Formula/mosaik.rb",
    b"templates/mosaik.rb.tmpl",
    b"README.md",
    b"SECURITY.md",
    b"LICENSE",
    b".gitignore",
}
DIRECTORIES = {b"Formula", b"templates", b".github"}


def verify_tree(repository, tree="HEAD"):
    entries = subprocess.run(
        ["git", "-C", str(repository), "ls-tree", "-r", "-t", "-z", tree],
        check=True, capture_output=True,
    ).stdout
    release = False
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, _object_id = metadata.split()
        if mode == b"040000" and kind == b"tree":
            allowed = path in DIRECTORIES or path.startswith(b".github/")
        elif mode in (b"100644", b"100755") and kind == b"blob":
            allowed = path in FILES or path.startswith(b".github/")
        else:
            raise ValueError(f"non-regular tree entry: {path!r} (mode {mode.decode()})")
        if not allowed:
            raise ValueError(f"path outside tap allowlist: {path!r}")
        if path == b"Formula/mosaik.rb":
            release = True
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        release = verify_tree(args.repository)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Tap tree rejected: {error}\n")
    print(f"release={str(release).lower()}")


if __name__ == "__main__":
    main()
