# Live Source Adapter Plane

OIS live sources are implemented as governed adapters over the existing Source Gateway.

## Supported adapters

- HTTP/REST
- polling with checkpoint-after-commit semantics
- webhook signature verification
- RSS/Atom
- files and exports
- DB-API compatible databases
- GitHub REST
- deterministic adapter registry

All adapters converge on SourceGateway.ingest(), which applies tenant scope, credentials, rate limits, deterministic evidence IDs, content hashing, durable evidence, and outbox publication.

## Production rules

1. Credentials are supplied by the credential boundary; adapters do not persist secrets.
2. Every source record becomes immutable raw evidence before downstream processing.
3. Polling checkpoints advance only after gateway acceptance.
4. Webhooks reject invalid signatures before ingestion.
5. Adapter failures remain observable and must not silently become knowledge.
6. Synthetic adapters may exercise the same contracts but cannot produce production verification.

## Extending the plane

A new platform should implement an adapter that converts its native response into a SourceRequest. Platform-specific parsing stays inside the adapter; authorization, provenance, evidence, idempotency, and outbox behavior stay in the Source Gateway.

## Next integrations

The same contracts can be used for streaming, CDC, object storage, browser acquisition, and platform-specific social APIs without changing downstream intelligence consumers.
