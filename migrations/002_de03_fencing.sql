-- DE-03: durable worker fencing primitives.
-- The lease epoch is the fencing token: every durable mutation must be
-- authorized by the currently active worker/epoch pair.

ALTER TABLE ois_idempotency_results
    ADD COLUMN IF NOT EXISTS worker_id TEXT,
    ADD COLUMN IF NOT EXISTS worker_epoch BIGINT;

DO $$
BEGIN
    IF to_regclass('public.ois_side_effect_outbox') IS NOT NULL THEN
        ALTER TABLE ois_side_effect_outbox
            ADD COLUMN IF NOT EXISTS worker_id TEXT,
            ADD COLUMN IF NOT EXISTS worker_epoch BIGINT;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ois_idempotency_worker_epoch_idx
    ON ois_idempotency_results (worker_id, worker_epoch);

CREATE INDEX IF NOT EXISTS ois_execution_leases_active_idx
    ON ois_execution_leases (execution_id, worker_id, lease_epoch, state, expires_at);
