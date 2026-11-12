# Mosaik from your terminal

Mosaik's command-line tool lets you sign in and use Mosaik products from a terminal.
It also lets an agent act with the access you give it.

The first release is being prepared. This repository holds a formula template;
installation becomes available when the first release pull request adds the formula.

## Install and sign in

On macOS or Linux with [Homebrew](https://brew.sh) installed:

```sh
brew tap mosaik/tap https://auth.mosaikhq.app/brew && brew trust --tap mosaik/tap && brew install mosaik
mosaik auth login
```

The `auth.mosaikhq.app/brew` address works from release 2.0.0. Until then, use the GitHub line below.

Your browser opens for sign-in. If you belong to more than one organisation,
choose the one to use. Homebrew installs Node 24 for you.

The install command uses Homebrew 7's explicit tap trust. If
`auth.mosaikhq.app` is unreachable, use the same repository through GitHub:

```sh
brew tap mosaik/tap https://github.com/Sakeliga/mosaic-homebrew && brew trust --tap mosaik/tap && brew install mosaik
```

Run `mosaik --help` for commands or `mosaik guide` for instructions for an agent.
Native Windows is not supported; use Linux through WSL.

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

Each [release](https://github.com/Sakeliga/mosaic-homebrew/releases) includes a
tarball, a standalone JavaScript file, a Sigstore bundle for each, and
`sbom.cdx.json`, a list of the bundled software dependencies. You need `curl`,
`shasum` and [cosign](https://docs.sigstore.dev/cosign/system_config/installation/)
for these checks (`brew install cosign` installs cosign).

Choose a published version and copy its 64-character `sha256` from
[Formula/mosaik.rb](Formula/mosaik.rb) at the reviewed commit for that version.
Replace both example values below. Run the commands in a new directory:

```sh
version=2.0.0
expected_sha256=REPLACE_WITH_THE_REVIEWED_FORMULA_SHA256
asset="mosaik-$version.tar.gz"
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
`node mosaik.mjs --version` with Node 24. The CLI includes its agent guide;
`guide.md` is also provided as a convenience copy.
The standalone `.mjs` has its own signature bundle; use its matching asset and
bundle names when checking it. The formula's hash is for the tarball only.

## How a version gets here

A release of the private source repository builds the CLI twice and checks
that both files match, checks the bundle's contents, then signs the release
files using Sigstore. A GitHub App publishes the files here and opens a pull
request rendering [the formula template](templates/mosaik.rb.tmpl) with the
release URL and sha256. Homebrew infers the version from the URL.

Release pull requests may change only the formula. Trusted checks use the
base branch's scripts and template, require an exact rendered match, and
check the release URL, downloaded hash and signing identity. Separate
unprivileged checks audit, install and test on macOS and Linux. A member of
the releasers team must review and approve the pull request before it reaches
`main`. Homebrew then installs the reviewed version using Node 24's explicit
path. See [.github/settings.md](.github/settings.md) for the protections and
their application status.

Pull requests that leave the formula unchanged run static checks of the
template, workflows and verification scripts, and need code-owner approval.
Any formula change requires all release checks, even for version `0.0.0`.

Rehearsals use prereleases tagged `rehearsal-v<X.Y.Z>-<run_id>-<run_attempt>` and pull requests
against `rehearsal`. Only that branch accepts signatures from the source
workflow's `rehearsal/*` branches. `main` accepts only `mosaik-v<version>`
releases signed at the matching `v<version>` source tag.

To report a vulnerability privately, see [SECURITY.md](SECURITY.md).
