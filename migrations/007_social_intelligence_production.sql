-- G1/G2 focused Social Intelligence production spine.
-- Schema is managed by the repository migration system; application code must not create these tables.

CREATE TABLE IF NOT EXISTS raw_evidence (
    evidence_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    connector_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    ingestion_run_id TEXT NOT NULL,
    UNIQUE (
        tenant_id,
        workspace_id,
        source_id,
        source_record_id,
        payload_hash
    )
);

CREATE TABLE IF NOT EXISTS source_outbox (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_source_outbox_pending
    ON source_outbox (created_at, event_id)
    WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS publication_ledger (
    publication_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    destination TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('pending', 'published', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    UNIQUE (destination, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_publication_ledger_event
    ON publication_ledger (event_id, destination);

CREATE TABLE IF NOT EXISTS social_intelligence_posts (
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (
        tenant_id,
        workspace_id,
        provider,
        platform,
        external_id
    )
);
