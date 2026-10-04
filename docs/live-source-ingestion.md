# Phase B — Live Source Ingestion

Phase B extends the API Source Socket without creating a parallel source stack.

## Runtime path

External webhook / polling scheduler -> WebhookGateway / PollingEngine -> SourceGateway
-> canonical event + idempotency + rate limits -> raw evidence + outbox -> SQLite / PostgreSQL

## Builds 7–13

- Build 7 — Webhook Gateway: validates bounded JSON webhook requests and routes accepted events through the existing SourceGateway.
- Build 8 — Production Polling Engine: schedules existing PollingSourceAdapter instances with bounded concurrency. Cursor ownership remains with the adapter and its durable cursor store.
- Build 9 — Source Registry / Control API: stores tenant/workspace-scoped source definitions and enables/disables/removes source configurations.
- Build 10 — Canonical Source Event Model: gives every source observation a stable event ID, payload hash, timestamps, schema version, and source identity.
- Build 11 — Idempotency + Deduplication: explicit delivery-key claims complement the existing evidence uniqueness constraint.
- Build 12 — Rate-Limit Manager: coordinates tenant/workspace/source token buckets while retaining the existing deterministic TokenBucket primitive.
- Build 13 — Webhook Security: verifies HMAC-SHA256 signatures, timestamp freshness, constant-time comparison, and replay keys before ingestion.

## Reliability invariants

1. Authentication remains outside generic adapters.
2. Tenant/workspace scope is preserved through every control and ingestion boundary.
3. Poll cursors advance only after SourceGateway acceptance.
4. Webhook requests are rejected before parsing/ingestion when signatures or replay checks fail.
5. Idempotency admission happens after rate admission so a rate-limited delivery does not consume its retry key.
6. Raw evidence and the outbox remain the durable acceptance boundary.
7. PostgreSQL remains the production persistence target; SQLite implementations are deterministic reference implementations and test fixtures.

## Source registration

Use SourceControlAPI for source configuration and ApiSourceSocket for live adapter execution. A source definition contains tenant/workspace scope, provider and source ID, acquisition mode (poll, webhook, or push), enabled state, credential reference, and provider configuration.

The control registry stores configuration; it does not persist credential secrets.

## Webhook signing

The Phase B default canonical signing input is timestamp + "." + raw_body.

The SHA-256 HMAC digest is sent with the configured signature prefix (default sha256=). Timestamp freshness and delivery-key replay protection are mandatory when the WebhookSecurity boundary is configured.

## Polling

PollingEngine owns scheduling and bounded concurrency. PollingSourceAdapter continues to own cursor semantics, so a successful page is checkpointed only after each accepted record has passed through the gateway. This keeps acquisition, durability, and scheduling separate.