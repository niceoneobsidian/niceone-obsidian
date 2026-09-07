-- OIS tenant isolation v1.
-- The application role must NOT own these tables; FORCE ROW LEVEL SECURITY
-- prevents the table owner from bypassing policies during application access.
-- Tenant context is transaction-local and must be set by trusted middleware.

CREATE OR REPLACE FUNCTION ois_current_tenant_id() RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT current_setting('app.current_tenant_id', true)
$$;

ALTER TABLE ois_execution_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_execution_checkpoints FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ois_execution_checkpoints_tenant_isolation ON ois_execution_checkpoints;
CREATE POLICY ois_execution_checkpoints_tenant_isolation
    ON ois_execution_checkpoints
    USING (tenant_id = ois_current_tenant_id())
    WITH CHECK (tenant_id = ois_current_tenant_id());

ALTER TABLE ois_idempotency_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_idempotency_results FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ois_idempotency_results_tenant_isolation ON ois_idempotency_results;
CREATE POLICY ois_idempotency_results_tenant_isolation
    ON ois_idempotency_results
    USING (tenant_id = ois_current_tenant_id())
    WITH CHECK (tenant_id = ois_current_tenant_id());

ALTER TABLE ois_side_effect_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_side_effect_outbox FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ois_side_effect_outbox_tenant_isolation ON ois_side_effect_outbox;
CREATE POLICY ois_side_effect_outbox_tenant_isolation
    ON ois_side_effect_outbox
    USING (tenant_id = ois_current_tenant_id())
    WITH CHECK (tenant_id = ois_current_tenant_id());
