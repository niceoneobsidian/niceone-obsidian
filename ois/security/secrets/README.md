# OIS Developer Credential Control Plane

Six security layers are now represented in the repository.

- P0 Foundation: taxonomy, environment separation, .env.example, repository scanning, metadata registry, OS keychain and log redaction.
- P1 API keys: generation, environment prefixes, SHA-256 digest storage, constant-time validation, scopes, expiry, revocation, rotation and audit events.
- P2 Secret Broker: provider-neutral access with local keychain, Infisical, Vault, AWS Secrets Manager, Azure Key Vault and Google Secret Manager adapters.
- P3 Runtime: bounded in-memory cache, invalidation, and child-process environment injection.
- P4 Governance: default-deny policy, RBAC, workload identity boundary, anomaly signals, rotation scheduler and incident containment.
- P5 Agent Security: agent identity, capability-scoped ephemeral credentials and approval gates.

Core invariant:

    IDENTITY -> POLICY -> CAPABILITY -> SECRET -> EXECUTION

Issued OIS API keys are hashed and are never persisted in raw form. External
provider credentials remain retrievable only through the broker and are not
placed in the metadata registry.

The modules are production-shaped foundations, not production verification.
Runtime, provider, CI, integration, rollback and deployment evidence must still
be established before claiming production readiness.
