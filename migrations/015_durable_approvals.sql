-- Phase D5 durable human approvals and restart-safe resume payload.

ALTER TABLE autonomous_approvals
    ADD COLUMN IF NOT EXISTS event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS source_id TEXT,
    ADD COLUMN IF NOT EXISTS event_type TEXT,
    ADD COLUMN IF NOT EXISTS run_id UUID;

CREATE INDEX IF NOT EXISTS autonomous_approvals_resume_idx
    ON autonomous_approvals (tenant_id, workspace_id, decision, expires_at);
