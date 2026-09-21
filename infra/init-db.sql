CREATE TABLE IF NOT EXISTS ois_execution_checkpoint_history (
    checkpoint_id UUID PRIMARY KEY,
    execution_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT,
    workflow_version TEXT,
    step_index INTEGER NOT NULL,
    status TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    state JSONB NOT NULL,
    state_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ois_checkpoint_history_execution
ON ois_execution_checkpoint_history
(tenant_id, execution_id, step_index DESC, created_at DESC);

CREATE OR REPLACE FUNCTION ois_reject_checkpoint_history_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'OIS checkpoint history is immutable';
END;
$$;

DROP TRIGGER IF EXISTS trg_ois_checkpoint_history_immutable
ON ois_execution_checkpoint_history;

CREATE TRIGGER trg_ois_checkpoint_history_immutable
BEFORE UPDATE OR DELETE ON ois_execution_checkpoint_history
FOR EACH ROW EXECUTE FUNCTION ois_reject_checkpoint_history_mutation();
