"""PostgreSQL schema for OIS production execution, evidence, security and backups."""

SQL = r'''
CREATE TABLE IF NOT EXISTS ois_execution (
  execution_id UUID PRIMARY KEY,
  tenant_id TEXT NOT NULL DEFAULT 'personal',
  capability TEXT NOT NULL,
  workflow_id TEXT,
  actor TEXT NOT NULL,
  state TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  request JSONB NOT NULL,
  result JSONB,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ois_execution_event (
  event_id UUID PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES ois_execution(execution_id) ON DELETE CASCADE,
  tenant_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ois_idempotency (
  tenant_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  execution_id UUID NOT NULL REFERENCES ois_execution(execution_id),
  result JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS ois_approval (
  approval_id UUID PRIMARY KEY,
  execution_id UUID NOT NULL REFERENCES ois_execution(execution_id),
  tenant_id TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('pending','approved','rejected')),
  actor TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE ois_execution ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_execution_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE ois_approval ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ois_execution_tenant ON ois_execution;
CREATE POLICY ois_execution_tenant ON ois_execution USING (tenant_id = current_setting('ois.tenant_id', true));
DROP POLICY IF EXISTS ois_event_tenant ON ois_execution_event;
CREATE POLICY ois_event_tenant ON ois_execution_event USING (tenant_id = current_setting('ois.tenant_id', true));
DROP POLICY IF EXISTS ois_idempotency_tenant ON ois_idempotency;
CREATE POLICY ois_idempotency_tenant ON ois_idempotency USING (tenant_id = current_setting('ois.tenant_id', true));
DROP POLICY IF EXISTS ois_approval_tenant ON ois_approval;
CREATE POLICY ois_approval_tenant ON ois_approval USING (tenant_id = current_setting('ois.tenant_id', true));
'''
