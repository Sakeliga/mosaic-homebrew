# Mosaik from your terminal

Mosaik's command-line tool lets you sign in and use Mosaik products from a terminal.
It also lets an agent act with the access you give it.

## Install and sign in

On macOS or Linux with [Homebrew](https://brew.sh) installed:

```sh
brew tap mosaik/tap https://auth.mosaikhq.app/brew && brew trust --tap mosaik/tap && brew install mosaik
mosaik auth login
```

Your browser opens for sign-in. If you belong to more than one organisation,
choose the one to use.

From release 2.1.0, Homebrew installs one file, `mosaik`, which needs nothing
else: no Node and no other formula. There is a binary for each of these:

| System | Processor |
| --- | --- |
| macOS | Apple Silicon (arm64) |
| macOS | Intel (x64) |
| Linux with glibc | x64 |
| Linux with glibc | arm64 |

Release 2.0.0 installed a script and Homebrew's Node 24 to run it. After
upgrading, `node@24` is no longer needed for `mosaik`; `brew autoremove`
removes it if nothing else on your machine uses it.

The install command uses Homebrew 7's explicit tap trust. If
`auth.mosaikhq.app` is unreachable, use the same repository through GitHub:

```sh
brew tap mosaik/tap https://github.com/Sakeliga/mosaic-homebrew && brew trust --tap mosaik/tap && brew install mosaik
```

Run `mosaik --help` for commands or `mosaik guide` for instructions for an agent.

## Other platforms

On a system without a binary (Alpine and other musl-based Linux, a 32-bit
machine, or anything else that runs Node), use the same CLI as one JavaScript
file with your own Node 24. Each release from 2.1.0 includes
`mosaik-<version>.cjs` and its signature. Verify it as described under
[Verify a download yourself](#verify-a-download-yourself), then run:

```sh
node mosaik-2.1.0.cjs --version
```

Native Windows is not supported; use Linux through WSL, where the Homebrew
line above works.

## Update or uninstall

```sh
brew update && brew upgrade mosaik
```

To sign out of all accounts on this machine and remove the tool:

```sh
mosaik auth logout --all
brew uninstall mosaik
brew untap mosaik/tap
```

## Verify a download yourself

Each [release](https://github.com/Sakeliga/mosaic-homebrew/releases) from 2.1.0
includes one tarball per platform (`mosaik-<version>-<platform>.tar.gz`), the
standalone `mosaik-<version>.cjs`, a Sigstore bundle for each of those five
files, and `sbom.cdx.json`, a list of the bundled software dependencies. You
need `curl`, `shasum` and
[cosign](https://docs.sigstore.dev/cosign/system_config/installation/) for
these checks (`brew install cosign` installs cosign).

Choose a published version and your platform: `darwin-arm64`, `darwin-x64`,
`linux-x64` or `linux-arm64`. Copy the 64-character `sha256` that follows your
platform's `url` in [Formula/mosaik.rb](Formula/mosaik.rb) at the reviewed
commit for that version. Replace the three example values below. Run the
commands in a new directory:

```sh
version=2.1.0
platform=linux-x64
expected_sha256=REPLACE_WITH_THE_REVIEWED_FORMULA_SHA256
asset="mosaik-$version-$platform.tar.gz"
release="https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v$version"
curl --fail --location --proto '=https' --proto-redir '=https' --output "$asset" "$release/$asset"
curl --fail --location --proto '=https' --proto-redir '=https' --output "$asset.sigstore.json" "$release/$asset.sigstore.json"
printf '%s  %s\n' "$expected_sha256" "$asset" | shasum --algorithm 256 --check -
cosign verify-blob "$asset" --bundle "$asset.sigstore.json" \
  --certificate-identity "https://github.com/Sakeliga/mosaic-auth/.github/workflows/deploy.yml@refs/tags/v$version" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Both checks must succeed before you extract or run the download. The hash ties
the download to the reviewed formula; the signature ties it to the release
workflow at that exact source tag. Cosign also checks the signing certificate
and transparency-log evidence. A valid signature for a different version fails.

For a server without Homebrew, verify the tarball as above, extract it, and run
`./mosaik --version`. No Node is needed. The tarball holds three files:
`mosaik`, `guide.md` and `LICENSE`. The CLI includes its agent guide;
`guide.md` is a convenience copy. Download with `curl` as shown: the macOS
binary is not notarised by Apple, so macOS blocks a copy downloaded through a
browser.

To check the standalone `mosaik-<version>.cjs`, set `asset="mosaik-$version.cjs"`
and run the two `curl` commands and the `cosign` command. The formula holds
hashes for the tarballs only, so the signature is the check for the `.cjs`.

Release 2.0.0 has a different layout: one `mosaik-2.0.0.tar.gz` holding
`mosaik.mjs`, which runs with Node 24.

## How a version gets here

A release of the private source repository builds the CLI for each platform
twice and checks that both builds match, checks the bundle's contents, then
signs the release files using Sigstore. A GitHub App publishes the files here
and opens a pull request rendering
[the formula template](templates/mosaik.rb.tmpl) with the version and each
platform's release URL and sha256.

Release pull requests may change only the formula. Trusted checks use the
base branch's scripts and template, require an exact rendered match, and
check every platform's release URL, downloaded hash and signing identity; one
platform failing fails the release. Separate unprivileged checks audit,
install and test on a machine of each platform. A member of the releasers team
must review and approve the pull request before it reaches `main`. See
[.github/settings.md](.github/settings.md) for the protections and their
application status.

Pull requests that leave the formula unchanged run static checks of the
template, workflows and verification scripts, and need code-owner approval.
Any formula change requires all release checks, even for version `0.0.0`.

Rehearsals use prereleases tagged `rehearsal-v<X.Y.Z>-<run_id>-<run_attempt>` and pull requests
against `rehearsal`. Only that branch accepts signatures from the source
workflow's `rehearsal/*` branches. `main` accepts only `mosaik-v<version>`
releases signed at the matching `v<version>` source tag.

To report a vulnerability privately, see [SECURITY.md](SECURITY.md).
