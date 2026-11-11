# Repository settings

`Sakeliga/mosaic-homebrew` distributes the Mosaik CLI. It stays private until
the rehearsal passes. The owner makes it public and applies the settings below;
committing these files does not apply them.

## Target

| Setting | Source | Effect |
| --- | --- | --- |
| `main: review` | `rulesets/main-review.json` | Pull request, one code-owner approval, latest-push approval, stale approvals dismissed, resolved threads, squash only. No bypass |
| `main: integrity` | `rulesets/main-integrity.json` | Signed commits, up-to-date `verify` check from GitHub Actions, no force push or deletion. No bypass |
| CLI release tags | `rulesets/tags.json` | Only `mosaic-auth-releasers` and the release GitHub App can create, update or delete `mosaik-v*` and `rehearsal-v*` tags |
| CODEOWNERS | `CODEOWNERS` | Every file requires `@Sakeliga/mosaic-auth-releasers` review; the team must have explicit write access |
| Immutable releases | Repository setting | Published release assets and tags cannot be replaced |
| Secret scanning and push protection | Repository setting | Enabled, including after the visibility change |
| Private vulnerability reporting | Repository setting | Enabled so reports can arrive without public issues |
| Fork pull requests | Actions settings | Every external contributor needs approval to run workflows; private forks receive neither secrets nor write tokens |
| Default workflow permissions | Actions settings | Read only; workflows cannot approve pull requests |
| Merges | Repository setting | Squash only; delete branches on merge |

The required check is the final job named `verify`. It fails unless both the
macOS and Linux release jobs succeed, including when a job is skipped or
cancelled. There is no placeholder-version exemption: `0.0.0` has no release,
so the bootstrap PR cannot prove installation. The first real evidence is the
lead's signed rehearsal, followed by the first production release PR.

The workflow uses `pull_request`, pinned actions, `contents: read`, and no
repository or environment secrets. Checkout does not persist credentials. The
short-lived read token is available only to the release-download step, so it
can retrieve private rehearsal assets. Formula Ruby is evaluated only after
the tarball hash and signature pass. The verified tarball seeds Homebrew's
download cache, allowing installation while the tap is still private.

`main` accepts only stable `X.Y.Z`, a `mosaik-vX.Y.Z` tap release and the exact
`mosaic-auth/.github/workflows/deploy.yml@refs/tags/vX.Y.Z` signing identity.
`rehearsal` accepts only `rehearsal-v<version>-<run>` tap releases and an
anchored identity under that same source workflow's `refs/heads/rehearsal/`.
The issuer is always `https://token.actions.githubusercontent.com`.
Rehearsal releases are prereleases and never update the default tap branch.

## GitHub App

The owner installs the release App on **this repository only**, with repository
Contents: write and Pull requests: write (Metadata: read is implicit). It
publishes assets and opens formula PRs. It has no bypass on either main ruleset
and cannot approve its own updates. The source repository holds the App's ID
and private key in its release environment; no App secret belongs in this tap.

## Apply

The following commands are for the owner, after reviewing the files. They
have not been run by the tap lane. Run from this repository's root. Ruleset
actor IDs of `0` are placeholders: supply the App's numeric **App ID**, not
its installation ID. The team ID is looked up by name.

```sh
R=Sakeliga/mosaic-homebrew
TEAM=$(gh api orgs/Sakeliga/teams/mosaic-auth-releasers --jq .id)
read -r -p 'Release GitHub App ID: ' APP_ID
test "$TEAM" -gt 0 && test "$APP_ID" -gt 0 || exit 1

gh api -X PUT orgs/Sakeliga/teams/mosaic-auth-releasers/repos/$R -f permission=push

for f in main-review main-integrity tags; do
  jq --argjson team "$TEAM" --argjson app "$APP_ID" '
    .bypass_actors |= map(
      if .actor_type == "Team" then .actor_id = $team
      elif .actor_type == "Integration" then .actor_id = $app
      else . end)
  ' ".github/rulesets/$f.json" |
    gh api -X POST "repos/$R/rulesets" --input -
done

gh api -X PUT "repos/$R/immutable-releases"
gh api -X PUT "repos/$R/private-vulnerability-reporting"
gh api -X PATCH "repos/$R" \
  -F allow_squash_merge=true -F allow_merge_commit=false \
  -F allow_rebase_merge=false -F delete_branch_on_merge=true
gh api -X PATCH "repos/$R" --input - <<'JSON'
{
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" }
  }
}
JSON
gh api -X PUT "repos/$R/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false
gh api -X PUT "repos/$R/actions/permissions/fork-pr-contributor-approval" \
  -f approval_policy=all_external_contributors
```

In **Settings → Actions → General → Fork pull request workflows**, require
approval for fork workflows and leave **Send write tokens** and **Send secrets**
off. In a private repository, enable running fork pull request workflows only
with those restrictions. Organisation policy may lock these settings more
strictly. Secret scanning, private reporting and related controls may depend
on repository visibility and the organisation's plan: record any unavailable
control, and enable and read it back before the tap is made available to users.
Do not interpret an API error as an applied setting.

For an existing ruleset, use `PUT repos/$R/rulesets/<id>` with the same JSON
instead of creating a duplicate. Bootstrap integration and creation of the
`rehearsal` branch are owner/lead steps, outside this lane. Apply the required
checks before merging any production formula update; never bypass a failing
release check to ship a version.

## Read back

Record the IDs and responses after application. Read each ruleset's full
details, not only the list summary:

```sh
gh api "repos/$R/rulesets" --jq '.[] | [.id, .name, .enforcement]'
gh api "repos/$R/rulesets/<id>"
gh api "repos/$R/rules/branches/main"
gh api "repos/$R/immutable-releases"
gh api "repos/$R/private-vulnerability-reporting"
gh api "repos/$R" --jq '{visibility, security_and_analysis, allow_squash_merge, allow_merge_commit, allow_rebase_merge, delete_branch_on_merge}'
gh api "repos/$R/actions/permissions/workflow"
gh api "repos/$R/actions/permissions/fork-pr-contributor-approval"
gh api "repos/$R/actions/permissions/fork-pr-workflows-private-repos"
```

The P3 rehearsal also demonstrates a wrong-hash PR failing `verify` and a
direct push to `main` being refused. These are evidence tasks for the lead,
not actions performed by the tap lane.

## Applied and read back

Not applied or read back by this change. The owner records application here,
including unavailable controls while private and their status after publication.
