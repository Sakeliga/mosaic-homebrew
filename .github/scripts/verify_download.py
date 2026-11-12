"""Verify downloaded bytes using metadata produced by the trusted proposal check."""

import argparse
import json
import subprocess
from pathlib import Path

from verify_release import verify_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    release = json.loads(args.proposal.read_text())
    if release["mode"] != "release":
        raise ValueError("download verification requires a release proposal")
    archive = args.directory / release["asset"]
    verify_digest(archive, release["sha256"])
    subprocess.run(["cosign", "verify-blob", str(archive), "--bundle", str(archive) + ".sigstore.json",
                    release["identity_flag"], release["identity"],
                    "--certificate-oidc-issuer", release["issuer"]], check=True)


if __name__ == "__main__":
    main()
