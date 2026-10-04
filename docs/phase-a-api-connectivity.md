# Phase A — Authentication & Real API Connectivity

Phase A establishes one reusable OAuth 2.0 boundary and governed real API sources.

## Builds

1. Credential & Auth Manager — PR #184.
2. OAuth2 Provider Framework — provider-neutral authorization-code flow, state validation, expiry, refresh, and secret-store boundaries.
3. GitHub Source — authenticated REST /user source.
4. TikTok Source — Login Kit OAuth + Display API source.
5. Meta/Facebook Source — Graph API /me source.
6. Google Source — Drive API files source.

## Runtime boundary

OAuth authorization
      |
      v
OAuth2Provider
      |
      v
OAuthCredentialStore
      |
      v
ApiSourceSocket
      |
      v
SourceAdapter
      |
      v
SourceGateway
      |
      +--> durable evidence
      |
      +--> durable outbox

Provider integrations own endpoint and scope configuration. Generic HTTP acquisition remains provider-agnostic. Tokens and client secrets are credential material and are never written into source evidence.

## Build 2 — reusable OAuth2 framework

The provider-neutral framework in ois/infrastructure/oauth2.py now provides:

- HTTPS-only provider endpoints, with localhost allowed for development redirects.
- Required client/redirect/scope validation.
- Cryptographically random authorization state.
- Tenant/workspace/provider binding.
- One-time state consumption.
- State expiration (10 minutes by default).
- Provider-specific request and response scope separators.
- client_secret_post and client_secret_basic token authentication.
- Structured provider/transport/response errors.
- Refresh-token preservation when a provider omits a replacement token.
- No retained raw token response payload.
- Explicit expiration timestamps.

The default InMemoryOAuth2StateStore is for tests/development. Production deployments must supply a shared durable state store so authorization callbacks can be handled by any application instance.

## Credential storage

InMemoryOAuthCredentialStore is development/test only.

Production deployments should use SecretManagerOAuthCredentialStore with an encrypted secret-manager backend. The backend is responsible for:

- encryption at rest;
- access control;
- audit logging;
- durable storage;
- secret rotation.

OIS enforces tenant/workspace/provider scope before returning token material to the source boundary.

## Automatic token refresh

OAuth2SourceConnection.ingest() checks token expiry before source execution. Credentials expiring within the configured refresh skew are refreshed first.

If a provider returns no replacement refresh token or scope, the existing values are preserved.

If an access token is expired and no refresh token exists, ingestion fails rather than sending known-expired credentials.

## Provider implementations

### GitHub

- Authorization: GitHub OAuth web application flow.
- Token exchange: GitHub OAuth access-token endpoint.
- Source: github.rest.user.
- Authenticated request: GET https://api.github.com/user.
- Scopes: read:user, user:email.

### TikTok

- Login Kit OAuth 2.0.
- Source: tiktok.display.v2.
- Scopes: user.info.basic, video.list.
- TikTok uses comma-separated scopes in the authorization and token response.
- Token exchange and refresh use the common OAuth2 framework.
- The existing Display API client remains responsible for TikTok's API-specific pagination/request shape.

### Meta/Facebook

- Meta Graph OAuth.
- Source: meta.graph.me.
- Graph API /me?fields=id,name,email.
- Scopes: public_profile, email.
- Graph API version is explicitly configured by the integration.

### Google

- Google OAuth 2.0 web-server flow.
- Source: google.drive.files.
- Default scope: https://www.googleapis.com/auth/drive.metadata.readonly.
- Requests offline access so refresh tokens can be retained.
- Drive pagination is handled by the source adapter.

## Real-provider validation

Normal CI never calls external providers.

Opt-in smoke tests live in tests/integrations/test_phase_a_live.py. To run them against real providers, provide protected access tokens and set:

OIS_LIVE_PHASE_A=1
OIS_LIVE_GITHUB_ACCESS_TOKEN=...
OIS_LIVE_TIKTOK_ACCESS_TOKEN=...
OIS_LIVE_META_ACCESS_TOKEN=...
OIS_LIVE_GOOGLE_ACCESS_TOKEN=...

These tests exercise the actual external API through the governed source boundary. They do not store the supplied tokens in the repository.

The complete browser OAuth callback flow still requires registered provider applications and real redirect URIs. The application must call begin(), send the user to the returned authorization URL, receive the callback code + state, call complete(), and then use the returned credential through ingest().

## Security invariant

OAuth client secret  -> secret manager only
OAuth refresh token  -> secret manager only
OAuth access token   -> credential boundary only
Source evidence      -> provider response only
Outbox               -> evidence reference / event metadata only

No generic source adapter handles authorization codes, refresh tokens, or provider client secrets.
