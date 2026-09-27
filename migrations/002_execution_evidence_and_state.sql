-- Durable execution state and append-only evidence.
-- Run after 001_durable_execution.sql.

CREATE TABLE IF NOT EXISTS execution_state (
    execution_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN (
        'pending', 'authorized', 'executing', 'validating', 'verified',
        'retry_pending', 'rollback_pending', 'escalation_required', 'failed'
    )),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_evidence (
    evidence_id BIGSERIAL PRIMARY KEY,
    execution_id TEXT NOT NULL,
    category TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS execution_evidence_execution_id_idx
    ON execution_evidence (execution_id, created_at);
