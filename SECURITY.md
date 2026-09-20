# Security Policy

## Scope

Niceone Obsidian is a governed AI execution and intelligence platform. Security reports are especially important for issues involving authorization, capability routing, tool execution, external side effects, persistence, recovery, evidence integrity, secrets, or supply-chain controls.

## Supported versions

This repository is under controlled implementation. Security fixes are prioritized for the default branch and the latest published release, if a release exists. Older commits and unreleased feature branches are not supported security baselines.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** for this repository when it is available. Do not open a public issue for an undisclosed vulnerability.

If private reporting is unavailable, open a minimal issue requesting a private contact channel without including exploit details. Maintainers will respond with a safe reporting path.

Please include:

- A concise description and impact assessment.
- Affected commit, tag, component, or configuration.
- Reproduction steps or a minimal proof of concept.
- Any required permissions, infrastructure, or data.
- Suggested mitigation, if known.

## Response expectations

Maintainers will acknowledge a report when practical, validate the issue, assign severity, and coordinate a fix or mitigation. Timelines depend on impact, reproducibility, and maintainer availability. Please allow responsible disclosure coordination before publishing details.

## Security principles

- Model output is a proposal, not infrastructure authority.
- Consequential actions require explicit authorization.
- Evidence and state transitions must remain auditable.
- Production changes require rollback paths.
- Secrets must never be committed to the repository, issue tracker, or logs.

## Scope limitations

Do not perform denial-of-service testing, social engineering, destructive testing, or access attempts against infrastructure that you do not own. Test only against local or explicitly authorized environments.
