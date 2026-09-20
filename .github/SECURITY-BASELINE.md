# Repository Security Baseline

## Implemented in repository

- Gitleaks secret detection workflow.
- Security policy and private reporting guidance.
- CODEOWNERS for security-sensitive paths.
- Least-privilege workflow permissions where defined.
- Immutable GitHub Action pinning enforcement.
- SBOM and artifact-attestation workflow.
- Dependency update configuration.
- Security-focused issue template.
- Evidence requirements for authorization, idempotency, recovery, and persistence.

## Required GitHub administration

The connected repository tool does not expose security-settings mutations. Enable in GitHub Settings:

1. Secret scanning.
2. Push protection.
3. Two-factor authentication requirements for maintainers/collaborators where supported by account or organization policy.
4. A main-branch ruleset requiring at least one approving PR review.
5. Required critical CI checks.
6. No force-pushes and no branch deletion on main.

The observed main ruleset is active and currently requires Run Tests and License Compliance Scan, but its pull-request approval count is zero. Update that setting in GitHub before treating review enforcement as complete.

## History secret verification

A clean working-tree scan does not prove the complete Git history is clean. Run a full-history Gitleaks scan and rotate any credential that has ever been exposed before enabling push protection.
