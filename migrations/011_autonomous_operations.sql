-- Phase C autonomous operations durable boundaries.
-- Workflow definitions and approval requests remain tenant/workspace scoped.

CREATE TABLE IF NOT EXISTS autonomous_workflows (
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'enabled',
    trigger_event_type TEXT NOT NULL,
    trigger_source_id TEXT,
    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, workspace_id, workflow_id, version),
    CHECK (status IN ('enabled', 'paused', 'disabled'))
);

CREATE INDEX IF NOT EXISTS autonomous_workflows_trigger_idx
    ON autonomous_workflows (tenant_id, workspace_id, trigger_event_type, status);

CREATE TABLE IF NOT EXISTS autonomous_approvals (
    approval_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    CHECK (decision IN ('pending', 'approved', 'rejected', 'expired'))
);

CREATE INDEX IF NOT EXISTS autonomous_approvals_scope_idx
    ON autonomous_approvals (tenant_id, workspace_id, decision, expires_at);

CREATE TABLE IF NOT EXISTS autonomous_workflow_runs (
    run_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, workspace_id, workflow_id, workflow_version, event_id)
);

CREATE INDEX IF NOT EXISTS autonomous_workflow_runs_scope_idx
    ON autonomous_workflow_runs (tenant_id, workspace_id, created_at);
