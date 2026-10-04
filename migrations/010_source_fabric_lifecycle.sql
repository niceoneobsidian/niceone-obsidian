-- Phase B Source Fabric lifecycle metadata.
-- Keeps existing source_registry rows compatible while adding explicit lifecycle state.

ALTER TABLE source_registry
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'enabled';

ALTER TABLE source_registry
    ADD COLUMN IF NOT EXISTS poll_interval_seconds DOUBLE PRECISION;

ALTER TABLE source_registry
    ADD COLUMN IF NOT EXISTS capabilities JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE source_registry
SET status = CASE WHEN enabled THEN 'enabled' ELSE 'disabled' END
WHERE status IS NULL OR status = '';

ALTER TABLE source_registry
    DROP CONSTRAINT IF EXISTS source_registry_status_check;

ALTER TABLE source_registry
    ADD CONSTRAINT source_registry_status_check
    CHECK (status IN ('registered', 'enabled', 'paused', 'degraded', 'disabled'));

CREATE INDEX IF NOT EXISTS source_registry_status_idx
    ON source_registry (tenant_id, workspace_id, status);
