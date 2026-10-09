# Runtime / Deployment / Rollback Evidence

Every production security release must retain evidence for:
1. Runtime: execution received, authorized, capability started/completed, checkpointed.
2. Deployment: release authorization, candidate activation and environment.
3. Rollback: rollback authorization, target version and rollback verification.
4. Credential: secret access, rotation and revocation/containment.
5. CI: Ruff, mypy, pytest, Gitleaks and security conformance results.

The canonical OIS lifecycle records Kernel events into the shared append-only evidence ledger. Deployment promotion and rollback are authorization-gated through the existing production Control Plane.

Release gate: a release is not production-verified until CI artifacts contain successful results for all five categories. Source structure alone is insufficient evidence.

Rollback invariant: candidate -> canary -> decision -> promote OR rollback -> evidence.

AWS Secrets Manager uses a create/set/test/finish rotation model and retains the previous known-good version during successful promotion; OIS follows the same verify-before-activate principle.
