-- Phase D1 durable autonomous workflow execution state.

ALTER TABLE autonomous_workflow_runs
    ADD COLUMN IF NOT EXISTS attempt INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE autonomous_workflow_runs
SET idempotency_key = tenant_id || ':' || workspace_id || ':' ||
                     workflow_id || ':' || workflow_version || ':' || event_id
WHERE idempotency_key IS NULL;

ALTER TABLE autonomous_workflow_runs
    ALTER COLUMN idempotency_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS autonomous_workflow_runs_idempotency_idx
    ON autonomous_workflow_runs (idempotency_key);

CREATE TABLE IF NOT EXISTS autonomous_workflow_idempotency (
    idempotency_key TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    run_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS autonomous_workflow_idempotency_scope_idx
    ON autonomous_workflow_idempotency (tenant_id, workspace_id, created_at);
