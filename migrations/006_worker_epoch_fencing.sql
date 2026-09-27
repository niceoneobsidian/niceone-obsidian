-- OIS DE-03 PostgreSQL worker lease / epoch fencing schema.

CREATE TABLE IF NOT EXISTS ois_worker_leases (
    execution_id UUID PRIMARY KEY,
    worker_id TEXT NOT NULL,
    epoch BIGINT NOT NULL CHECK (epoch > 0),
    lease_expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ois_worker_leases_expiry
    ON ois_worker_leases (lease_expires_at);
