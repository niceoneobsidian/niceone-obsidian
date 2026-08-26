CREATE TABLE IF NOT EXISTS ois_execution_checkpoints (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT,
    workflow_version TEXT,
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ois_execution_checkpoints_tenant
    ON ois_execution_checkpoints (tenant_id);

CREATE INDEX IF NOT EXISTS idx_ois_execution_checkpoints_status
    ON ois_execution_checkpoints (status);
