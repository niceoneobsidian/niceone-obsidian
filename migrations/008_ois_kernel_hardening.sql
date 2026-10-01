CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS ois_graph_state_store (
    tenant_id UUID NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    checkpoint_bytes BYTEA NOT NULL,
    fencing_token BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, thread_id, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS ois_attestation_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    sequence_no BIGINT NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    previous_hash VARCHAR(64) NOT NULL DEFAULT repeat('0', 64),
    event_hash VARCHAR(64) NOT NULL,
    context_snapshot JSONB NOT NULL,
    attestation_signature VARCHAR(512) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, thread_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS ois_kernel_dead_letter_queue (
    dlq_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    thread_id VARCHAR(255) NOT NULL,
    last_scenario_id VARCHAR(64) NOT NULL,
    error_diagnostic_log TEXT NOT NULL,
    frozen_context_data JSONB NOT NULL,
    cryptographic_seal_signature VARCHAR(512) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ois_artifact_registry (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    workflow_name VARCHAR(128) NOT NULL,
    version_tag VARCHAR(64) NOT NULL,
    manifest_payload JSONB NOT NULL,
    provenance_hash VARCHAR(64) NOT NULL,
    supervisor_promotion_signature VARCHAR(512) NOT NULL,
    promoted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, workflow_name, version_tag)
);

ALTER TABLE ois_graph_state_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_attestation_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_kernel_dead_letter_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_artifact_registry ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_state_select ON ois_graph_state_store;
DROP POLICY IF EXISTS tenant_state_insert ON ois_graph_state_store;
DROP POLICY IF EXISTS tenant_state_update ON ois_graph_state_store;
CREATE POLICY tenant_state_select ON ois_graph_state_store FOR SELECT
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
CREATE POLICY tenant_state_insert ON ois_graph_state_store FOR INSERT
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
CREATE POLICY tenant_state_update ON ois_graph_state_store FOR UPDATE
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);

DROP POLICY IF EXISTS tenant_evidence_select ON ois_attestation_evidence;
DROP POLICY IF EXISTS tenant_evidence_insert ON ois_attestation_evidence;
CREATE POLICY tenant_evidence_select ON ois_attestation_evidence FOR SELECT
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
CREATE POLICY tenant_evidence_insert ON ois_attestation_evidence FOR INSERT
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);

DROP POLICY IF EXISTS tenant_dlq_select ON ois_kernel_dead_letter_queue;
DROP POLICY IF EXISTS tenant_dlq_insert ON ois_kernel_dead_letter_queue;
CREATE POLICY tenant_dlq_select ON ois_kernel_dead_letter_queue FOR SELECT
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
CREATE POLICY tenant_dlq_insert ON ois_kernel_dead_letter_queue FOR INSERT
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);

DROP POLICY IF EXISTS tenant_registry_select ON ois_artifact_registry;
DROP POLICY IF EXISTS tenant_registry_insert ON ois_artifact_registry;
CREATE POLICY tenant_registry_select ON ois_artifact_registry FOR SELECT
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
CREATE POLICY tenant_registry_insert ON ois_artifact_registry FOR INSERT
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);

CREATE OR REPLACE FUNCTION ois_prevent_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'OIS immutable ledger: UPDATE/DELETE forbidden';
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

DROP TRIGGER IF EXISTS lock_registry_ledger ON ois_artifact_registry;
CREATE TRIGGER lock_registry_ledger
BEFORE UPDATE OR DELETE ON ois_artifact_registry
FOR EACH ROW EXECUTE FUNCTION ois_prevent_mutation();
