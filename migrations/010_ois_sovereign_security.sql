-- OIS sovereign security baseline, derived from PostgreSQL/RLS security patterns.
-- Tenant identity MUST be established by trusted ingress before application queries.
-- Never expose a privileged database role to model output, agents, or clients.

CREATE SCHEMA IF NOT EXISTS ois;

CREATE OR REPLACE FUNCTION ois.current_tenant_id() RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('ois.tenant_id', true), '');
$$;

ALTER TABLE IF EXISTS ois_execution_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ois_idempotency_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ois_side_effect_outbox ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ois_checkpoint_tenant_isolation ON ois_execution_checkpoints;
CREATE POLICY ois_checkpoint_tenant_isolation ON ois_execution_checkpoints
  USING (tenant_id = ois.current_tenant_id())
  WITH CHECK (tenant_id = ois.current_tenant_id());

DROP POLICY IF EXISTS ois_idempotency_tenant_isolation ON ois_idempotency_results;
CREATE POLICY ois_idempotency_tenant_isolation ON ois_idempotency_results
  USING (tenant_id = ois.current_tenant_id())
  WITH CHECK (tenant_id = ois.current_tenant_id());

DROP POLICY IF EXISTS ois_outbox_tenant_isolation ON ois_side_effect_outbox;
CREATE POLICY ois_outbox_tenant_isolation ON ois_side_effect_outbox
  USING (tenant_id = ois.current_tenant_id())
  WITH CHECK (tenant_id = ois.current_tenant_id());

-- Defense in depth: force policies even for table owners where appropriate.
-- Apply to application-owned roles only after validating migration ownership.
-- ALTER TABLE ois_execution_checkpoints FORCE ROW LEVEL SECURITY;
-- ALTER TABLE ois_idempotency_results FORCE ROW LEVEL SECURITY;
-- ALTER TABLE ois_side_effect_outbox FORCE ROW LEVEL SECURITY;

-- Per-operation security tests belong in CI/deployment validation:
-- 1. tenant A cannot SELECT/UPDATE tenant B rows.
-- 2. tenant A cannot INSERT a row stamped tenant B.
-- 3. privileged maintenance access is isolated from application roles.
-- 4. missing tenant context fails closed.
