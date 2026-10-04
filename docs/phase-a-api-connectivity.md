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
