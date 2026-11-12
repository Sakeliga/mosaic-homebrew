"""Verify downloaded bytes using metadata produced by the trusted proposal check."""

import argparse
import json
import subprocess
from pathlib import Path

from verify_release import verify_digest


def verify_downloads(release, directory, cosign="cosign"):
    """Check every platform's tarball: its hash, then its signature. Any one failure fails all."""
    if release["mode"] != "release":
        raise ValueError("download verification requires a release proposal")
    if not release["assets"]:
        raise ValueError("a release proposal names at least one platform")
    for asset in release["assets"]:
        archive = directory / asset["asset"]
        verify_digest(archive, asset["sha256"])
        subprocess.run([cosign, "verify-blob", str(archive), "--bundle", str(archive) + ".sigstore.json",
                        release["identity_flag"], release["identity"],
                        "--certificate-oidc-issuer", release["issuer"]], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    verify_downloads(json.loads(args.proposal.read_text()), args.directory)


if __name__ == "__main__":
    main()
