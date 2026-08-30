-- OIS Social Growth production schema. Apply through the deployment migration system.
CREATE TABLE IF NOT EXISTS social_events (
    event_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    external_id TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_events_external
    ON social_events(platform, external_id) WHERE external_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS social_metric_observations (
    observation_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    platform TEXT,
    source_event_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_social_metrics_entity_metric_time
    ON social_metric_observations(entity_id, metric, observed_at DESC);

CREATE TABLE IF NOT EXISTS social_attribution_results (
    conversion_id TEXT NOT NULL,
    touchpoint_id TEXT NOT NULL,
    credit DOUBLE PRECISION NOT NULL,
    total_value DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (conversion_id, touchpoint_id)
);

CREATE TABLE IF NOT EXISTS social_experiments (
    experiment_id TEXT PRIMARY KEY,
    hypothesis TEXT NOT NULL,
    metric TEXT NOT NULL,
    definition JSONB NOT NULL,
    status TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS social_memory_records (
    key TEXT NOT NULL,
    version INTEGER NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (key, version)
);
