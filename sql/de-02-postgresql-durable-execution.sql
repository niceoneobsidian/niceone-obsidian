-- DE-02 PostgreSQL durable execution schema.
-- This schema mirrors the Kernel CheckpointStore and IdempotencyStore contracts.

CREATE TABLE IF NOT EXISTS ois_checkpoints (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT,
    workflow_version TEXT,
    context JSONB NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ois_idempotency_results (
    invocation_id TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ois_checkpoints_tenant_idx
    ON ois_checkpoints (tenant_id);

CREATE INDEX IF NOT EXISTS ois_checkpoints_updated_idx
    ON ois_checkpoints (updated_at DESC);
