# Credential & Auth Manager

The Credential & Auth Manager is the single credential boundary for live source integrations.

## Responsibility

Provider connectors declare a credential reference, authentication scheme, scheme options, and optionally a provider-specific authenticator. They do not resolve secrets or implement credential storage.

Flow:

Provider Connector -> ApiSourceSocket -> SourceGateway -> CredentialAuthManager -> CredentialResolver -> Authenticator -> HTTP request

## Security boundary

- Credential records contain references, not secret material.
- Resolution is tenant-scoped.
- Empty credentials are rejected.
- Generic HTTP adapters do not receive raw credential material.
- Authentication is applied through SourceGateway.authenticate_request().
- Provider-specific signing can be supplied as an Authenticator without changing generic adapters.

## Adding a provider

A provider integration declares its authentication policy, for example AuthPolicy(scheme=AuthScheme.OAUTH2).

A provider that needs a custom signer supplies an Authenticator implementation. Facebook, TikTok, Google, and future providers therefore use the same credential boundary instead of adding provider-specific authentication branches to generic source adapters.

## Production secret stores

InMemoryCredentialResolver is for tests/development only. Production deployments should implement CredentialResolver against the deployment's secret manager or vault. The resolver contract keeps storage outside the source gateway and provider connectors.
