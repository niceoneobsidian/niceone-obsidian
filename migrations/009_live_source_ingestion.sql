-- Phase B live source ingestion control and delivery deduplication.

CREATE TABLE IF NOT EXISTS source_registry (
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    mode TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    credential_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, workspace_id, source_id),
    CONSTRAINT source_registry_mode_check CHECK (mode IN ('poll', 'webhook', 'push'))
);

CREATE TABLE IF NOT EXISTS source_idempotency (
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    event_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, workspace_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS source_registry_enabled_idx
    ON source_registry (tenant_id, workspace_id, enabled);

CREATE INDEX IF NOT EXISTS source_idempotency_created_idx
    ON source_idempotency (created_at);
