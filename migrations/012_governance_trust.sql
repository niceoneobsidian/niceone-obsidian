-- Phase F governance/trust primitives.
CREATE TABLE IF NOT EXISTS agent_identities (
    tenant_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    trust_level TEXT NOT NULL DEFAULT 'standard',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (tenant_id, agent_id)
);

CREATE TABLE IF NOT EXISTS capability_grants (
    tenant_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    allowed_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    expires_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, agent_id, capability_id),
    FOREIGN KEY (tenant_id, agent_id) REFERENCES agent_identities(tenant_id, agent_id)
);

CREATE TABLE IF NOT EXISTS policy_versions (
    tenant_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    version TEXT NOT NULL,
    rules JSONB NOT NULL,
    content_hash TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, policy_id, version)
);

CREATE TABLE IF NOT EXISTS decision_provenance (
    decision_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    policy_id TEXT,
    policy_version TEXT,
    capability_id TEXT,
    inputs_digest TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS governance_audit (
    event_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    outcome TEXT NOT NULL,
    execution_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS autonomous_budgets (
    tenant_id TEXT NOT NULL,
    budget_id TEXT NOT NULL,
    max_cost DOUBLE PRECISION NOT NULL CHECK (max_cost >= 0),
    spent_cost DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (spent_cost >= 0),
    PRIMARY KEY (tenant_id, budget_id)
);

CREATE TABLE IF NOT EXISTS autonomous_action_limits (
    tenant_id TEXT NOT NULL,
    action TEXT NOT NULL,
    max_count BIGINT NOT NULL CHECK (max_count >= 0),
    window_seconds BIGINT NOT NULL CHECK (window_seconds > 0),
    PRIMARY KEY (tenant_id, action)
);

CREATE TABLE IF NOT EXISTS compliance_evidence (
    evidence_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    control_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    digest TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS governance_slos (
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    target DOUBLE PRECISION NOT NULL CHECK (target >= 0 AND target <= 1),
    metric TEXT NOT NULL,
    window_seconds BIGINT NOT NULL CHECK (window_seconds > 0),
    PRIMARY KEY (tenant_id, name)
);

ALTER TABLE agent_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE capability_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_provenance ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE autonomous_budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE autonomous_action_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance_slos ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_identities_tenant_isolation ON agent_identities USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY capability_grants_tenant_isolation ON capability_grants USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY policy_versions_tenant_isolation ON policy_versions USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY decision_provenance_tenant_isolation ON decision_provenance USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY governance_audit_tenant_isolation ON governance_audit USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY autonomous_budgets_tenant_isolation ON autonomous_budgets USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY autonomous_action_limits_tenant_isolation ON autonomous_action_limits USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY compliance_evidence_tenant_isolation ON compliance_evidence USING (tenant_id = current_setting('ois.tenant_id', true));
CREATE POLICY governance_slos_tenant_isolation ON governance_slos USING (tenant_id = current_setting('ois.tenant_id', true));
