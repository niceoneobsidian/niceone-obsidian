-- OIS Kernel production resilience storage contract.
-- Apply with a dedicated migration role; application roles must not own these tables.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS ois_graph_state_store (
    thread_id VARCHAR(255) NOT NULL,
    tenant_id UUID NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    checkpoint_bytes BYTEA NOT NULL,
    active_fencing_token BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS ois_hitl_gates (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(255) NOT NULL,
    tenant_id UUID NOT NULL,
    required_role VARCHAR(100) NOT NULL,
    proposed_side_effect JSONB NOT NULL,
    side_effect_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    resolution VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (resolution IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
    supervisor_signature VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ois_attestation_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    sequence_no BIGINT GENERATED ALWAYS AS IDENTITY,
    event_type VARCHAR(128) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    context_snapshot JSONB NOT NULL,
    previous_event_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    attestation_signature VARCHAR(512) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, thread_id, sequence_no),
    UNIQUE (tenant_id, thread_id, event_hash)
);

CREATE TABLE IF NOT EXISTS ois_kernel_dead_letter_queue (
    dlq_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_scenario_id VARCHAR(64) NOT NULL,
    error_diagnostic_log TEXT NOT NULL,
    frozen_context_data JSONB NOT NULL,
    context_hash VARCHAR(64) NOT NULL,
    cryptographic_seal_signature VARCHAR(512) NOT NULL
);

CREATE TABLE IF NOT EXISTS ois_lease_collision_audit (
    collision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    stale_token VARCHAR(64) NOT NULL,
    current_active_token VARCHAR(64) NOT NULL,
    attempted_action VARCHAR(100) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Every read/write must be tenant-scoped. FORCE RLS prevents table owners from
-- silently bypassing the policy in application sessions.
ALTER TABLE ois_graph_state_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_graph_state_store FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_hitl_gates ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_hitl_gates FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_attestation_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_attestation_evidence FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_kernel_dead_letter_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_kernel_dead_letter_queue FORCE ROW LEVEL SECURITY;
ALTER TABLE ois_lease_collision_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_lease_collision_audit FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_state ON ois_graph_state_store;
DROP POLICY IF EXISTS tenant_isolation_gates ON ois_hitl_gates;
DROP POLICY IF EXISTS tenant_isolation_evidence ON ois_attestation_evidence;
DROP POLICY IF EXISTS tenant_isolation_dlq ON ois_kernel_dead_letter_queue;
DROP POLICY IF EXISTS tenant_isolation_collision ON ois_lease_collision_audit;

CREATE POLICY tenant_isolation_state ON ois_graph_state_store
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation_gates ON ois_hitl_gates
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation_evidence ON ois_attestation_evidence
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation_dlq ON ois_kernel_dead_letter_queue
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
CREATE POLICY tenant_isolation_collision ON ois_lease_collision_audit
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE OR REPLACE FUNCTION ois_prevent_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'CRITICAL SECURITY VIOLATION: append-only ledger mutation is forbidden';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS lock_evidence_ledger ON ois_attestation_evidence;
CREATE TRIGGER lock_evidence_ledger
BEFORE UPDATE OR DELETE ON ois_attestation_evidence
FOR EACH ROW EXECUTE FUNCTION ois_prevent_mutation();

DROP TRIGGER IF EXISTS lock_dlq_ledger ON ois_kernel_dead_letter_queue;
CREATE TRIGGER lock_dlq_ledger
BEFORE UPDATE OR DELETE ON ois_kernel_dead_letter_queue
FOR EACH ROW EXECUTE FUNCTION ois_prevent_mutation();

DROP TRIGGER IF EXISTS lock_collision_ledger ON ois_lease_collision_audit;
CREATE TRIGGER lock_collision_ledger
BEFORE UPDATE OR DELETE ON ois_lease_collision_audit
FOR EACH ROW EXECUTE FUNCTION ois_prevent_mutation();

CREATE INDEX IF NOT EXISTS idx_dlq_tenant_lookup
    ON ois_kernel_dead_letter_queue (tenant_id, failed_at);
CREATE INDEX IF NOT EXISTS idx_evidence_tenant_thread
    ON ois_attestation_evidence (tenant_id, thread_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_collision_tenant_thread
    ON ois_lease_collision_audit (tenant_id, thread_id, recorded_at);
