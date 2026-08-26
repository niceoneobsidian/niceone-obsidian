CREATE TABLE IF NOT EXISTS ois_events (
    event_id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    tenant TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    provenance JSONB NOT NULL,
    correlation_id UUID,
    execution_id UUID,
    policy_context JSONB NOT NULL,
    validation JSONB NOT NULL,
    content_hash CHAR(64) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_ois_events_tenant_timestamp ON ois_events (tenant, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ois_events_execution ON ois_events (tenant, execution_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ois_events_correlation ON ois_events (tenant, correlation_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ois_events_type ON ois_events (tenant, event_type, timestamp DESC);

CREATE TABLE IF NOT EXISTS ois_execution_checkpoints (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, execution_id)
);
CREATE INDEX IF NOT EXISTS idx_ois_checkpoints_tenant_updated
    ON ois_execution_checkpoints (tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ois_world_entities (
    entity_id UUID PRIMARY KEY,
    tenant TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance_refs TEXT[] NOT NULL DEFAULT '{}',
    observed_at TIMESTAMPTZ NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    UNIQUE (tenant, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_ois_world_entities_tenant_type ON ois_world_entities (tenant, entity_type);

CREATE TABLE IF NOT EXISTS ois_world_relations (
    relation_id UUID PRIMARY KEY,
    tenant TEXT NOT NULL,
    subject_id UUID NOT NULL,
    predicate TEXT NOT NULL,
    object_id UUID NOT NULL,
    provenance_refs TEXT[] NOT NULL DEFAULT '{}',
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    FOREIGN KEY (tenant, subject_id) REFERENCES ois_world_entities(tenant, entity_id),
    FOREIGN KEY (tenant, object_id) REFERENCES ois_world_entities(tenant, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_ois_world_rel_subject ON ois_world_relations (tenant, subject_id);
CREATE INDEX IF NOT EXISTS idx_ois_world_rel_object ON ois_world_relations (tenant, object_id);

CREATE TABLE IF NOT EXISTS ois_knowledge_assertions (
    assertion_id UUID PRIMARY KEY,
    tenant TEXT NOT NULL,
    subject_id UUID NOT NULL,
    predicate TEXT NOT NULL,
    value JSONB NOT NULL,
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    authority TEXT NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    version INTEGER NOT NULL CHECK (version > 0),
    FOREIGN KEY (tenant, subject_id) REFERENCES ois_world_entities(tenant, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_ois_knowledge_subject ON ois_knowledge_assertions (tenant, subject_id, predicate);

COMMENT ON TABLE ois_events IS 'Append-only canonical OIS perception events.';
COMMENT ON TABLE ois_execution_checkpoints IS 'Durable tenant-scoped OIS execution state.';
COMMENT ON TABLE ois_world_entities IS 'Ground operational semantic state; authoritative observations only.';
COMMENT ON TABLE ois_world_relations IS 'Ground semantic relationships with provenance and temporal validity.';
COMMENT ON TABLE ois_knowledge_assertions IS 'Derived/learned knowledge kept separate from ground operational state.';
