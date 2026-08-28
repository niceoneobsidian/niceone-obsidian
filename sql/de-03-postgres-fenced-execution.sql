-- DE-03: durable worker ownership with monotonically increasing fencing epochs.
-- This migration is idempotent and matches ois.kernel.postgres._SCHEMA.

CREATE TABLE IF NOT EXISTS ois_execution_leases (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS ois_execution_leases_expiry_idx
    ON ois_execution_leases (expires_at);
CREATE INDEX IF NOT EXISTS ois_execution_leases_worker_idx
    ON ois_execution_leases (worker_id);

-- A fenced mutation must match execution_id + worker_id + lease_epoch and an
-- unexpired active lease. Never use worker_id alone as an ownership check.
