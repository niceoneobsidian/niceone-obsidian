-- OIS governed runtime schema: tenant isolation, HITL gates, and append-only evidence.
-- Runtime MUST set app.current_tenant_id with set_config(..., true) inside each transaction.

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

-- Existing durable checkpoint state is also tenant-scoped.
ALTER TABLE ois_execution_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_execution_checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_execution_checkpoint_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_execution_checkpoint_history FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_idempotency_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_idempotency_results FORCE ROW LEVEL SECURITY;

ALTER TABLE ois_hitl_gates ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_hitl_gates FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_runtime_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_runtime_evidence FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ois_checkpoint_tenant_policy ON ois_execution_checkpoints;
CREATE POLICY ois_checkpoint_tenant_policy ON ois_execution_checkpoints
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text);

DROP POLICY IF EXISTS ois_checkpoint_history_tenant_policy ON ois_execution_checkpoint_history;
CREATE POLICY ois_checkpoint_history_tenant_policy ON ois_execution_checkpoint_history
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text);

DROP POLICY IF EXISTS ois_idempotency_tenant_policy ON ois_idempotency_results;
CREATE POLICY ois_idempotency_tenant_policy ON ois_idempotency_results
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::text);

DROP POLICY IF EXISTS ois_hitl_tenant_policy ON ois_hitl_gates;
CREATE POLICY ois_hitl_tenant_policy ON ois_hitl_gates
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS ois_evidence_tenant_policy ON ois_runtime_evidence;
CREATE POLICY ois_evidence_tenant_policy ON ois_runtime_evidence
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- Evidence is append-only: no UPDATE/DELETE is permitted through the application role.
REVOKE UPDATE, DELETE ON ois_runtime_evidence FROM PUBLIC;

-- The application must use parameterized set_config, never string interpolation:
-- SELECT set_config('app.current_tenant_id', %s, true);
