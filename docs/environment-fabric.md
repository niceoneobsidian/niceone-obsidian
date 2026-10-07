# OIS Environment Fabric

OIS environments are governed execution profiles, not merely different env files.

## Profiles
- local: developer execution; external writes off.
- test: deterministic CI; external writes hard-blocked.
- staging: production-like, controlled integrations, protected deployment.
- production: external secret provider, explicit authorization, rollback and evidence.

.env.example contains non-secret configuration and secret placeholders only.
.env.local is ignored by Git. Production values are injected by the deployment
secret manager. ois.config.settings.validate_startup() is the startup gate.

Credential classes:
- Public configuration -> repository/config schema
- Identifiers -> environment/deployment variables
- Application secrets -> secret manager
- User/provider OAuth tokens -> encrypted credential store
- Signing/encryption keys -> secret manager/KMS

External writes default to disabled. Writes require explicit enablement, approval,
verified capability evidence, staging/production scope, and non-dry-run execution.

Activation is OFF -> SHADOW -> CANARY -> LIMITED -> PRODUCTION.
Production requires implementation, tests, integration, deployment, policy,
rollback and production-verification evidence.

CI validates configuration, runs tests and secret scanning. Deployment jobs target
GitHub staging and production environments. Configure required reviewers and
environment secrets in GitHub repository settings.

The repository already contains Vault/Kubernetes deployment scaffolding. The
application boundary remains provider-neutral and defines a workload identity
contract for short-lived credentials.
