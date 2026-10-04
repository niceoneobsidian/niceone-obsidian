# OIS API Source Socket

The API Source Socket is the single application-facing entry point for governed
live external sources.

## Architecture

```text
External API / Webhook / Poller
            |
            v
     ApiSourceSocket
            |
            v
   SourceAdapterRegistry
            |
            v
      Source Adapter
            |
            v
       SourceGateway
        /        \
       v          v
 Raw Evidence   Outbox
       \          /
        \        /
         v      v
       PostgreSQL / durable store
```

## Responsibilities

- **ApiSourceSocket**: registration, discovery, health, and ingestion facade.
- **SourceAdapterRegistry**: deterministic connector lifecycle and lookup.
- **Source adapters**: provider-specific acquisition such as HTTP, polling,
  webhooks, RSS, GitHub, files, and databases.
- **SourceGateway**: tenant/workspace authorization, credential resolution,
  rate limits, canonical hashing, durable evidence, and outbox creation.
- **Credentials**: connectors receive a credential reference; secret material
  is resolved only at the credential boundary.
- **Evidence + outbox**: every accepted source record enters the same durable
  ingestion path.

## Adding a connector

Implement the existing `SourceAdapter` contract and register it:

```python
from ois.infrastructure.source_gateway.socket import ApiSourceSocket

socket.register(my_adapter)
result = socket.ingest(
    "provider:source",
    tenant_id="tenant-1",
    workspace_id="workspace-1",
)
```

The adapter must not persist credentials or bypass `SourceGateway`.

## Live acquisition modes

The existing adapter plane supports:

- request/response HTTP
- incremental polling with cursor checkpoints
- signed webhooks
- RSS/news feeds
- GitHub
- database and file sources

Provider-specific integrations remain under `ois/integrations/`; the socket
is the shared control boundary rather than another provider implementation.

## Reliability rules

1. Source records are identified deterministically from tenant, workspace,
   source, record ID, and canonical payload hash.
2. Duplicate evidence is rejected idempotently.
3. Polling cursors advance only after gateway ingestion succeeds.
4. Webhooks must pass signature verification before ingestion.
5. Credential references are tenant-scoped.
6. Durable production storage should use the existing PostgreSQL source ledger
   and outbox path.
7. Consumers of the outbox must remain idempotent because publication is
   at-least-once.

## Next hardening boundary

Provider-specific authentication schemes should be represented explicitly
(API key, bearer/OAuth2, HMAC, or provider-specific signing) rather than
embedding secrets in generic adapter headers. This is the next step before
adding additional production providers.

## Authentication boundary

Authentication is a first-class source concern, but it is not implemented inside generic adapters.
Connectors declare an authentication scheme and options; the shared authentication boundary applies them to transport requests.

Supported schemes:

- **API key** — adds a configured key to a named header such as `X-API-Key`.
- **Bearer** — sends the current access token as `Authorization: Bearer ...`.
- **OAuth2** — uses the same bearer transport, while token exchange/refresh remains in a provider OAuth client or token service. Generic adapters never handle authorization codes or refresh tokens.
- **HMAC/provider signing** — signs a canonical request with a tenant-scoped secret. Provider-specific header names/prefixes are configuration on the signer, not code in the HTTP adapter.

The credential path is:

`CredentialRef -> SourceGateway -> CredentialResolver -> CredentialMaterial -> Authenticator -> HTTP request`

Secrets remain outside source records. The adapter receives resolved material only for the outbound request and the durable gateway still records the source payload/evidence, never the credential itself.

Example declarative connector configuration:

```python
HttpSourceAdapter(
    source_id="example:api",
    url="https://api.example.com/v1/items",
    auth_scheme=AuthScheme.BEARER,
)
```

For OAuth2, the connector supplies the current access-token credential; refresh and provider-specific token exchange stay in the provider integration layer. This keeps Facebook, TikTok, Google, GitHub, and custom providers from adding authentication branches to generic adapters.
