# OIS Free-Tier Governance

## Status

The private repository currently does not have enforceable GitHub rulesets under the available account plan. This is a platform/account limitation, not evidence that `main` is protected.

## Policy

Until server-side protection is available, OIS treats these controls as mandatory engineering policy:

1. Work on a dedicated branch.
2. Open a pull request for changes intended for `main`.
3. Require the CI validation workflow to pass before treating a change as merge-ready.
4. Run the deterministic governance gate locally before publishing a change.
5. Never represent GitHub server-side branch protection as enabled unless a live direct-push rejection test proves it.
6. Preserve failed governance tests as audit evidence without leaving test markers on `main`.

## Evidence boundary

The governance gate is an executable CI/local control. It is **not** a substitute for GitHub's server-side branch protection. The project must retain this distinction in audits and readiness reports.

## Upgrade path

If the repository later moves to an account/organization plan that supports enforceable rulesets, enable them for `main` and repeat the direct-push rejection plus PR/CI acceptance tests. Only then may the server-side protection control be marked verified.
