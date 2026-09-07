CREATE TABLE IF NOT EXISTS ois_execution_checkpoint_history (
    checkpoint_id UUID PRIMARY KEY,
    execution_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT,
    workflow_version TEXT,
    step_index INTEGER NOT NULL,
    status TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    state JSONB NOT NULL,
    state_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ois_checkpoint_history_execution
ON ois_execution_checkpoint_history
(tenant_id, execution_id, step_index DESC, created_at DESC);

CREATE OR REPLACE FUNCTION ois_reject_checkpoint_history_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'OIS checkpoint history is immutable';
END;
$$;

DROP TRIGGER IF EXISTS trg_ois_checkpoint_history_immutable
ON ois_execution_checkpoint_history;

CREATE TRIGGER trg_ois_checkpoint_history_immutable
BEFORE UPDATE OR DELETE ON ois_execution_checkpoint_history
FOR EACH ROW EXECUTE FUNCTION ois_reject_checkpoint_history_mutation();

CREATE TABLE IF NOT EXISTS ois_hitl_gates (
    gate_id UUID PRIMARY KEY,
    execution_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    action_type TEXT NOT NULL,
    required_role TEXT NOT NULL,
    proposed_side_effect JSONB NOT NULL,
    side_effect_hash TEXT NOT NULL CHECK (length(side_effect_hash) = 64),
    plan_hash TEXT NOT NULL CHECK (length(plan_hash) = 64),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    expires_at TIMESTAMPTZ NOT NULL,
    reviewed_by_user_id UUID,
    reviewed_at TIMESTAMPTZ,
    cryptographic_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ois_runtime_evidence (
    evidence_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    execution_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    sequence_no BIGINT NOT NULL,
    previous_hash TEXT,
    provenance_hash TEXT NOT NULL CHECK (length(provenance_hash) = 64),
    evidence_payload JSONB NOT NULL,
    signed_by_supervisor TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, execution_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS idx_ois_hitl_gates_tenant_execution
ON ois_hitl_gates (tenant_id, execution_id, status);
CREATE INDEX IF NOT EXISTS idx_ois_runtime_evidence_tenant_execution
ON ois_runtime_evidence (tenant_id, execution_id, sequence_no);

-- Tenant RLS is applied by infra/migrations/002_governed_runtime.sql after the
-- application transaction boundary has been wired to set app.current_tenant_id.
-- Do not enable RLS here prematurely: existing persistence tests intentionally
-- exercise the store before a tenant-aware connection context is installed.
