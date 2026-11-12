# Repository settings

`Sakeliga/mosaic-homebrew` distributes the Mosaik CLI. It stays private until
the rehearsal passes. The owner makes it public and applies settings;
committing these files does not apply them. The applied record below distinguishes
the protections read back on 2026-11-11 from the pending check-name update.

## Target

| Setting | Source | Effect |
| --- | --- | --- |
| `main: review` | `rulesets/main-review.json` | Pull request, one code-owner approval, latest-push approval, stale approvals dismissed, resolved threads, squash only. No bypass |
| `main: integrity` | `rulesets/main-integrity.json` | Signed commits, up-to-date `verify` and `trusted-release` checks from GitHub Actions, no force push or deletion. No bypass |
| CLI release tags | `rulesets/tags.json` | Only `mosaic-auth-releasers` and the release GitHub App can create, update or delete `mosaik-v*` and `rehearsal-v*` tags |
| CODEOWNERS | `CODEOWNERS` | Every file requires `@Sakeliga/mosaic-auth-releasers` review; the team must have explicit write access |
| Immutable releases | Repository setting | Published release assets and tags cannot be replaced |
| Secret scanning and push protection | Repository setting | Enabled, including after the visibility change |
| Private vulnerability reporting | Repository setting | Enabled so reports can arrive without public issues |
| Fork pull requests | Actions settings | Every external contributor needs approval to run workflows; private forks receive neither secrets nor write tokens |
| Default workflow permissions | Actions settings | Read only; workflows cannot approve pull requests |
| Merges | Repository setting | Squash only; delete branches on merge |

Two checks are required, both from GitHub Actions (integration ID `15368`):

| Required name | Workflow / job | Evidence |
| --- | --- | --- |
| `trusted-release` | `verify.yml` / `trusted-release`, on `pull_request_target` | Trusted tree, change isolation, base-template, release hash and signature checks |
| `verify` | `homebrew.yml` / `verify`, on `pull_request` | Both OS static jobs and every applicable installation job passed; also today's bootstrap check |

`trusted-release` is reserved for the trusted job; no head-defined job in this
repository uses that name. The owner must add `trusted-release` to the existing
required `verify` check immediately after the bootstrap merge (commands below).
Until then, `verify` continues to satisfy the current ruleset for PR #1.

Required checks are matched by name and GitHub App, not by workflow ownership.
Residual risk: a workflow-changing PR can publish any check name, including a
competing `trusted-release` result. The real trusted job rejects any formula
change combined with `.github/**` or any other changed path; a workflow change
must be separate from a formula change and needs a code owner's approval.
Reviewers must inspect workflow changes for competing check names rather than
treating a green name as proof of its origin. This design also relies on the
release App having **no Workflows permission**, checked below, so its token
cannot add or modify a workflow to publish a competing result.

If `Formula/mosaik.rb` differs from the event's base commit, it must be the
only changed path. A combined formula plus template, script, workflow, or
documentation change fails and names the other paths. Removing the formula
also fails. The proposed formula must match the **base commit's template**
byte for byte, then its downloaded hash and signature must pass. There is no
version exemption, including `0.0.0`.

If the formula is unchanged, trusted verification checks the tree and selects
static mode. Proposed template/script/workflow changes run their static tests,
template style and workflow lint in the separate unprivileged workflow, and
still require code-owner approval. A template update therefore lands separately
before a release can render it. Static mode is not evidence of installation.

Before selecting either mode or invoking Homebrew, verification checks every
entry in the proposed head's Git tree against a closed allowlist:
`Formula/mosaik.rb`, `templates/mosaik.rb.tmpl`, `.github/**`, `README.md`,
`SECURITY.md`, `LICENSE`, and `.gitignore`, plus their parent directories.
Only regular files and directories are permitted; symlinks and submodules
are rejected everywhere, including inside `.github`. Alternate formula paths,
casks, external Homebrew commands, aliases and migration/rename maps fail this
check. Only the allowed flat formula path can select release mode, so a nested
formula cannot be mistaken for bootstrap or shadow the verified formula.

The trust boundary relies on `pull_request_target` running the workflow owned
by the repository's **default branch**, rather than the pull request's workflow.
For PRs into `main`, this is the base branch's workflow. GitHub changed the
behavior for other base branches on 2025-12-08: the workflow still comes from
the default branch. See [GitHub's event change](https://github.blog/changelog/2025-11-07-actions-pull_request_target-and-environment-branch-protections-changes/).
The workflow explicitly checks out the event's base SHA for its scripts and
template, including for `rehearsal`; that base must remain owner-controlled.

The trusted job fetches the exact event head into a separate bare Git repository
under the runner's temporary directory. It never checks out, imports or executes
PR files: `git ls-tree`, `git diff` and `git show` inspect them as data. A moved
head fails closed. The job uses `contents: read` only, no secrets or environment,
no persisted checkout credentials, and no Actions cache reads or writes.
The read token is available only during Git fetch and private-release download.
The pinned cosign installer and signature verification execute trusted tooling;
downloaded assets are never executed in this job.

Installation stays on `pull_request`, with the same read-only permissions and
no secrets. Fresh installation runners repeat the **base** policy, template,
hash and signature checks for the event's exact head before checking it out or
running Homebrew. They do not consume PR-written metadata or a shared cache
from static checks. Only these unprivileged runners seed a local Homebrew
download cache with the verified tarball for private-release installation.

The trusted workflow must exist on the default branch before it can run.
PR #1's original base (`80ff308`) contains only README.md. Its head-defined
`verify` is the bootstrap check; it does not prove that `trusted-release` has
run. The approved order is: the owner merges #1 under today's ruleset with
`verify` green; immediately applies the ruleset update below; then the lead
proves activation with two never-merged PRs. There is no fallback that runs
head-owned checker code as trusted verification.

`main` accepts only stable `X.Y.Z`, a `mosaik-vX.Y.Z` tap release and the exact
`mosaic-auth/.github/workflows/deploy.yml@refs/tags/vX.Y.Z` signing identity.
`rehearsal` accepts only `rehearsal-v<X.Y.Z>-<run_id>-<run_attempt>` tap releases and an
anchored identity under that same source workflow's `refs/heads/rehearsal/`.
The issuer is always `https://token.actions.githubusercontent.com`.
Rehearsal releases are prereleases and never update the default tap branch.
The formula version is inferred from the tarball filename and must equal the
version in the tag. Both branches require numeric `X.Y.Z`, with no SemVer
prerelease suffix. A new run attempt gets a new immutable release tag.

## Formula rendering contract

`templates/mosaik.rb.tmpl` is the complete formula. `{{url}}` and `{{sha256}}`
are required, `{{version}}` is optional, and each may occur more than once.
No other `{{` is allowed. Rendering replaces those literals and preserves
every other byte, including the trailing newline. The source release job
performs the same substitution itself and executes nothing from this tap.
This tap's verification uses `.github/scripts/render_formula.py`.

Inputs must match these full patterns:

```text
version: [0-9]+\.[0-9]+\.[0-9]+
sha256: [0-9a-f]{64}
url: https://github\.com/Sakeliga/mosaic-homebrew/releases/download/(mosaik-v|rehearsal-v)[0-9A-Za-z.-]+/mosaik-[0-9.]+\.tar\.gz
```

Release verification then applies the stricter branch-specific tag and
filename rules above. Formula changes outside template substitutions fail;
changes to the Ruby must be reviewed in a separate template-only PR before
the release PR. The flat tarball contains `mosaik.mjs`, `guide.md` and `LICENSE`.
The guide is embedded in the CLI; `share/mosaik/guide.md` is a convenience copy.

## GitHub App

The release App is installed on **this repository only**, with repository
Contents: write and Pull requests: write (Metadata: read is implicit), and
**no Workflows permission**. This is a security property of the design: a stolen
App token cannot add or modify `.github/workflows/` to spoof a required check.
Do not grant Workflows permission when creating or updating the App. It
publishes assets and opens formula PRs. It has no bypass on either main ruleset
and cannot approve its own updates. The source repository holds the App's ID
and private key in its release environment; no App secret belongs in this tap.

The owner must read back the installation permissions and check the exact
permission set before activation and after any App permission change:

```sh
gh api --paginate orgs/Sakeliga/installations \
  --jq '.installations[] | select(.app_id == 5717044) | {id, app_id, repository_selection, permissions, html_url}'
gh api --paginate --slurp orgs/Sakeliga/installations | jq -e '
  [.[].installations[] | select(.app_id == 5717044)] |
  length == 1 and
  (.[0].repository_selection == "selected") and
  (.[0].permissions == {"contents":"write", "pull_requests":"write", "metadata":"read"})
'
```

The assertion rejects a `workflows` grant or any other extra permission. Open
the returned installation `html_url` and confirm the only selected repository
is `Sakeliga/mosaic-homebrew`. The lane has not run these organization-admin
reads; record the owner's result with the activation evidence.

## Apply

The following commands are for the owner, after reviewing the files. They
have not been run by the tap lane. Run from this repository's root. Ruleset
actor IDs of `0` are placeholders: supply the App's numeric **App ID**, not
its installation ID. The team ID is looked up by name.

```sh
R=Sakeliga/mosaic-homebrew
TEAM=$(gh api orgs/Sakeliga/teams/mosaic-auth-releasers --jq .id)
printf 'Release GitHub App ID: '
read -r APP_ID
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

### Pending required-check update

Immediately after the owner merges bootstrap PR #1, update the existing
integrity ruleset from `verify` alone to **`verify` and `trusted-release`**.
From the reviewed checkout, run exactly:

```sh
gh api -X PUT repos/Sakeliga/mosaic-homebrew/rulesets/27056786 \
  --input .github/rulesets/main-integrity.json
gh api repos/Sakeliga/mosaic-homebrew/rulesets/27056786 \
  --jq '.rules[] | select(.type == "required_status_checks") | .parameters'
gh api repos/Sakeliga/mosaic-homebrew/rules/branches/main
```

Expected contexts are `verify` and `trusted-release`, each with integration ID `15368`,
strict up-to-date checks, and no bypass. The JSON preserves signed commits,
no deletion and no force push. This update has **not** been applied by this PR.

### Activation checks after the bootstrap merge

The lead opens two throwaway PRs against `main`, both from the newly merged
base, and **never merges either**:

| Probe | Expected result |
| --- | --- |
| Add or change `Formula/mosaik.rb` and also change `templates/mosaik.rb.tmpl` | `trusted-release` fails, naming the template as another changed path, before any download or formula execution |
| Change only `templates/mosaik.rb.tmpl` in a way that still passes style and rendering tests | `trusted-release` passes in static mode; both OS static checks and the ordinary `verify` pass |

Inspect the trusted run's event (`pull_request_target`), default-branch workflow
source and event base/head SHAs, not only the check name. Record both PR URLs,
heads and run URLs alongside the ruleset and App permission read-backs. These
probes prove activation of the base-owned boundary; signed download and actual
installation remain part of the release rehearsal.

At publication, also retry the controls unavailable while private:

```sh
gh api -X PUT repos/Sakeliga/mosaic-homebrew/private-vulnerability-reporting
gh api -X PUT repos/Sakeliga/mosaic-homebrew/actions/permissions/fork-pr-contributor-approval \
  -f approval_policy=all_external_contributors
gh api repos/Sakeliga/mosaic-homebrew/private-vulnerability-reporting
gh api repos/Sakeliga/mosaic-homebrew/actions/permissions/fork-pr-contributor-approval
```

### Actions event policy at publication

When the repository becomes public, the owner must explicitly permit the
trusted workflow's `pull_request_target` event. Private repositories are exempt
from GitHub's default block; the default public policy is in evaluate mode
until enforcement on **2026-12-02**. The following creates a repository-scoped
policy for this workflow only and reads it back:

```sh
tap_policy_id=$(gh api -X POST repos/Sakeliga/mosaic-homebrew/actions/policies --jq .id --input - <<'JSON'
{
  "name": "Mosaik trusted release verification",
  "enforcement": "active",
  "conditions": {
    "workflow_path": {"include": [".github/workflows/verify.yml"], "exclude": []}
  },
  "rules": [{
    "type": "restrict_action_events",
    "parameters": {"allowed_events": ["pull_request_target"]}
  }]
}
JSON
)
gh api "repos/Sakeliga/mosaic-homebrew/actions/policies/$tap_policy_id"
gh api --paginate repos/Sakeliga/mosaic-homebrew/actions/policies
```

If this named policy already exists, use `PUT` with its ID instead of creating
a duplicate. Read back the active enforcement, exact workflow path and allowed
event; inspect inherited policies in the list too, since a stricter parent
policy also needs the owner's attention. Then repeat the passing activation
probe and retain its trusted run URL. If permission is missing after the
enforcement date, `trusted-release` will not run or report: its required check
remains missing, so nothing can merge. This fails closed.
See [GitHub's event policy documentation](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
and [policy API](https://docs.github.com/en/rest/actions/policies).

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

The P3 rehearsal also demonstrates a wrong-hash PR failing `trusted-release` and a
direct push to `main` being refused. These are evidence tasks for the lead,
not actions performed by the tap lane.

## Applied and read back

2026-11-11 — applied and read back by the owner; recorded here from the lead's
supplied evidence (the tap lane did not rerun repository administration calls):

- Team `mosaic-auth-releasers`, ID `20255150`, members `chrislemmer` and
  `t-alberts`, has push access.
- Rulesets `main: review` (`27056785`), `main: integrity` (`27056786`) and
  `CLI release tags` (`27056789`) are active. The applied integrity rule requires
  the existing `verify` check only; adding `trusted-release` remains pending above.
- GitHub App **Mosaik tap release**, App ID `5717044`, is installed on this
  repository only.
- Immutable releases enabled; read-back response: `{"enabled":true}`.
- Squash-only merges and delete-branch-on-merge enabled.
- Secret scanning and push protection enabled.
- Private vulnerability reporting was not applied: the API returned `404`
  while private. Fork pull request contributor approval was not applied:
  the API returned `422` while private. Apply both when the repository becomes
  public; neither error is recorded as success.
