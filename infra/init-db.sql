CREATE TABLE IF NOT EXISTS ois_workflow_checkpoints (
    checkpoint_id UUID PRIMARY KEY,
    execution_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    state_snapshot JSONB NOT NULL,
    snapshot_sha256 CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ois_execution_steps
ON ois_workflow_checkpoints (tenant_id, execution_id, step_index DESC, created_at DESC);

CREATE OR REPLACE FUNCTION ois_reject_checkpoint_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'OIS checkpoints are immutable';
END;
$$;

DROP TRIGGER IF EXISTS trg_ois_checkpoint_immutable ON ois_workflow_checkpoints;
CREATE TRIGGER trg_ois_checkpoint_immutable
BEFORE UPDATE OR DELETE ON ois_workflow_checkpoints
FOR EACH ROW EXECUTE FUNCTION ois_reject_checkpoint_mutation();
