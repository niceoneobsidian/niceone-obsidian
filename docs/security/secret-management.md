# OIS Secret Management Plane

The secret-management plane is the only OIS boundary allowed to materialize
runtime secrets.

## Layers

1. Canonical registry: `config/secrets/registry.toml`
2. SecretManager: one API for get/require/validate/health
3. Providers: environment for local/CI; Vault KV v2 for production
4. Lifecycle: rotation and revocation
5. Health: unified readiness/expiry/validation status
6. CI scanning: Gitleaks scans repository history on push and pull request

Credential references remain separate from secret values. Tenant/workspace
authorization continues to be enforced by the existing CredentialResolver and
SourceGateway.

Production Vault credentials must be supplied by the deployment environment;
they are never committed to the repository.

## Lifecycle

DISCOVER -> REGISTER -> STORE -> RESOLVE -> USE -> HEALTH -> ROTATE -> REVOKE

A leak must trigger immediate provider-side revocation/rotation. Secret
scanning detects exposure; it does not replace credential revocation.
