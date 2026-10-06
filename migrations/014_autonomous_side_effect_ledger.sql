-- Phase D4 durable side-effect ledger.

CREATE TABLE IF NOT EXISTS autonomous_side_effect_ledger (
    effect_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    run_id UUID NOT NULL,
    invocation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    capability_id TEXT NOT NULL,
    request JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'prepared',
    result JSONB,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CHECK (status IN ('prepared', 'processing', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS autonomous_side_effect_ledger_scope_idx
    ON autonomous_side_effect_ledger (tenant_id, workspace_id, run_id, created_at);
