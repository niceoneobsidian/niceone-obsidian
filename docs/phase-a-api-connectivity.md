# Phase A — Authentication & Real API Connectivity

Phase A establishes one provider-neutral OAuth 2.0 boundary and governed real API sources.

## Builds

1. Credential & Auth Manager — PR #184.
2. OAuth2 Provider Framework — provider-neutral authorization-code flow with state validation and refresh.
3. GitHub Source — authenticated REST /user source.
4. TikTok Source — existing Display API integration plus common OAuth2 provider configuration.
5. Meta/Facebook Source — Graph API /me source.
6. Google Source — Drive API files source.

## Runtime boundary

OAuth provider -> credential/token store -> ApiSourceSocket -> SourceAdapter -> SourceGateway -> durable evidence/outbox.

Provider integrations own endpoint and scope configuration. Generic HTTP acquisition remains provider-agnostic. Tokens and client secrets are credential material and are never written into source evidence.

## Activation

Register the provider source with ApiSourceSocket and provide a tenant-scoped credential ID containing the current access token. OAuth authorization and refresh happen through the provider OAuth object; the resulting token is persisted by the deployment credential store.

Official API references:
- GitHub REST authentication and authenticated-user endpoint.
- TikTok Login Kit and Display API.
- Google OAuth 2.0 web-server flow.
- Meta Graph API OAuth configuration is versioned and supplied by the integration.


## Phase A.1 — GitHub authenticated vertical slice

The first production-shaped acceptance slice is implemented by
`OAuth2SourceConnection` in `ois/infrastructure/oauth2_connection.py`.

The application flow is:

1. `begin()` creates a tenant/workspace-bound OAuth state and authorization URL.
2. `complete()` consumes that state, exchanges the authorization code, and writes the resulting token to the credential store.
3. `ingest()` resolves the tenant/workspace/provider-scoped credential and invokes `ApiSourceSocket`.
4. `GitHubSource` applies the access token through the governed `SourceGateway`.
5. `SourceGateway` writes raw evidence and the outbox event through the same `SQLiteSourceLedger` transaction in the reference implementation.
6. The access token remains credential material and is not copied into evidence or outbox payloads.

The acceptance tests in `tests/infrastructure/test_oauth2_connection.py` cover the complete
GitHub-shaped flow plus state replay, cross-workspace credential isolation, token refresh,
and credential non-leakage into evidence.

### Credential storage boundary

`InMemoryOAuthCredentialStore` exists only for development and deterministic tests. It
implements the credential resolver contract so the vertical slice can be exercised without
a secret-management service.

Production deployments must provide an `OAuthCredentialStore` backed by the deployment's
encrypted secret manager. The interface deliberately keeps access/refresh tokens outside
source definitions and durable source evidence.

### Production acceptance

The remaining environment-level step is to wire the same service to a real GitHub OAuth
application and a production credential store, then run the flow with real authorization
and the GitHub `/user` endpoint. GitHub's web flow returns a temporary callback code plus
the supplied state, which the application must validate before exchanging the code for a
user access token. See the GitHub OAuth web application flow documentation for the current
provider behavior.
