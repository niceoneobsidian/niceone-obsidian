-- OIS HITL admission + attestation schema.
-- Tenant context is supplied per transaction with set_config('app.current_tenant_id', ..., true).

CREATE TABLE IF NOT EXISTS ois_hitl_gates (
    gate_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    execution_id UUID NOT NULL,
    workflow_version TEXT NOT NULL,
    required_role TEXT NOT NULL,
    side_effect_hash TEXT NOT NULL,
    resolution TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (resolution IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    supervisor_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ois_hitl_gates_tenant_execution
    ON ois_hitl_gates (tenant_id, execution_id);

CREATE TABLE IF NOT EXISTS ois_attestation_evidence (
    evidence_id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    execution_id UUID NOT NULL,
    gate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    context_snapshot JSONB NOT NULL,
    attestation_signature TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ois_attestation_evidence_tenant_execution
    ON ois_attestation_evidence (tenant_id, execution_id, created_at);

ALTER TABLE ois_hitl_gates ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_attestation_evidence ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ois_hitl_gate_tenant_isolation ON ois_hitl_gates;
CREATE POLICY ois_hitl_gate_tenant_isolation ON ois_hitl_gates
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS ois_attestation_evidence_tenant_isolation ON ois_attestation_evidence;
CREATE POLICY ois_attestation_evidence_tenant_isolation ON ois_attestation_evidence
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- Evidence is append-only: callers may insert but cannot mutate/delete historical proof.
CREATE OR REPLACE FUNCTION ois_reject_attestation_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'OIS attestation evidence is immutable';
END;
$$;

DROP TRIGGER IF EXISTS trg_ois_attestation_immutable ON ois_attestation_evidence;
CREATE TRIGGER trg_ois_attestation_immutable
BEFORE UPDATE OR DELETE ON ois_attestation_evidence
FOR EACH ROW EXECUTE FUNCTION ois_reject_attestation_mutation();
