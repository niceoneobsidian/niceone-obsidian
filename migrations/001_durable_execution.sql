-- OIS Durable Execution v1 PostgreSQL schema.
-- Apply with the deployment migration runner or call
-- PostgresDurableExecutionStore.initialize() for development bootstrap.

CREATE TABLE IF NOT EXISTS ois_execution_checkpoints (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT,
    workflow_version TEXT,
    status TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    state JSONB NOT NULL,
    state_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ois_checkpoints_tenant
    ON ois_execution_checkpoints (tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ois_idempotency_results (
    invocation_id TEXT PRIMARY KEY,
    execution_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ois_side_effect_outbox (
    effect_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    execution_id UUID NOT NULL,
    invocation_id TEXT NOT NULL UNIQUE,
    capability_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    request JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    locked_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    last_error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ois_outbox_pending
    ON ois_side_effect_outbox (status, created_at);
