CREATE TABLE IF NOT EXISTS ois_checkpoints (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    checkpoint_version BIGINT NOT NULL CHECK (checkpoint_version > 0),
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ois_checkpoints_tenant_updated
    ON ois_checkpoints (tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ois_idempotency (
    invocation_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'COMPLETED')),
    result_json JSONB,
    lease_until TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (status = 'PENDING' AND result_json IS NULL)
        OR (status = 'COMPLETED' AND result_json IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_ois_idempotency_pending_lease
    ON ois_idempotency (lease_until)
    WHERE status = 'PENDING';
