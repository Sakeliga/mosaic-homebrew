"""Verify downloaded bytes using metadata produced by the trusted proposal check."""

import argparse
import json
import struct
import subprocess
import tarfile
import zlib
from pathlib import Path

from verify_release import verify_digest

ENTRIES = {"mosaik", "guide.md", "LICENSE"}

# Executable headers, read as data. A platform is "<system>-<processor>"; the
# system picks the file format and the processor picks the CPU field's value.
MACH_O_64 = 0xFEEDFACF            # little-endian 64-bit Mach-O; a universal file has another magic
MACH_O_EXECUTE = 2
MACH_O_CPU = {"arm64": 0x0100000C, "x64": 0x01000007}
ELF_EXECUTABLE = (2, 3)           # ET_EXEC, and ET_DYN for a position-independent executable
ELF_MACHINE = {"arm64": 183, "x64": 62}


def executable_matches(header, platform):
    """Whether these first bytes are a 64-bit executable for exactly this platform.

    Only the header is read, so a file that is nothing but a header passes.
    That is enough here: the bytes are already bound to the release by hash and
    signature, and this check exists to catch a wrong platform's file, not a
    forged program.
    """
    system, _, processor = platform.partition("-")
    if system == "darwin" and processor in MACH_O_CPU and len(header) >= 16:
        magic, cpu, _subtype, kind = struct.unpack_from("<IIII", header)
        return magic == MACH_O_64 and cpu == MACH_O_CPU[processor] and kind == MACH_O_EXECUTE
    if system == "linux" and processor in ELF_MACHINE and len(header) >= 20:
        kind, machine = struct.unpack_from("<HH", header, 16)
        # Bytes 4 and 5: 64-bit class, little-endian data.
        return (header[:6] == b"\x7fELF\x02\x01" and kind in ELF_EXECUTABLE
                and machine == ELF_MACHINE[processor])
    return False


def verify_contents(archive, platform):
    """Read the tarball as data: exactly the three regular files, and this platform's executable.

    A signature binds a file to the release, not to a platform. Without this
    check another platform's signed tarball, or the signed `.cjs`, would pass
    in this platform's place.
    """
    seen = set()
    try:
        with tarfile.open(archive, mode="r:gz") as tar:
            for member in tar:
                if member.name not in ENTRIES or member.name in seen:
                    raise ValueError(f"{archive.name}: unexpected or repeated entry {member.name!r}")
                if not member.isreg():
                    raise ValueError(f"{archive.name}: {member.name} is not a regular file")
                seen.add(member.name)
                if member.name == "mosaik":
                    header = tar.extractfile(member).read(32)
                    if not executable_matches(header, platform):
                        raise ValueError(f"{archive.name}: mosaik is not a 64-bit executable for {platform}")
    except (tarfile.TarError, EOFError, OSError, zlib.error) as error:
        raise ValueError(f"{archive.name}: not a readable gzip tarball: {error}") from error
    if seen != ENTRIES:
        raise ValueError(f"{archive.name}: missing {', '.join(sorted(ENTRIES - seen))}")


def verify_downloads(release, directory, cosign="cosign"):
    """Check every platform's tarball: hash, signature, then contents. Any one failure fails all."""
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
        verify_contents(archive, asset["platform"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    verify_downloads(json.loads(args.proposal.read_text()), args.directory)


if __name__ == "__main__":
    main()
