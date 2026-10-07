-- Phase D3 crash recovery and checkpoint heartbeat state.

ALTER TABLE autonomous_workflow_runs
    ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS recovery_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS autonomous_workflow_runs_recovery_idx
    ON autonomous_workflow_runs (status, last_heartbeat_at, next_attempt_at);
