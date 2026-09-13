-- Social Genome relational/vector persistence boundary.
-- Apply through the OIS migration runner. No graph vendor is required.
-- Generated taxonomies remain candidates until evidence/promotion gates validate them.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS social_genome_nodes (
    node_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    node_kind TEXT NOT NULL CHECK (node_kind IN ('chromosome', 'gene', 'topic', 'community', 'entity')),
    parent_node_id UUID REFERENCES social_genome_nodes(node_id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    keywords TEXT[] NOT NULL DEFAULT '{}',
    audience_segments TEXT[] NOT NULL DEFAULT '{}',
    platforms TEXT[] NOT NULL DEFAULT '{}',
    language TEXT,
    evidence_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (evidence_status IN ('candidate', 'observed', 'validated', 'deprecated')),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (confidence >= 0 AND confidence <= 1),
    observation_count BIGINT NOT NULL DEFAULT 0 CHECK (observation_count >= 0),
    embedding VECTOR(1536),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_social_genome_nodes_parent
    ON social_genome_nodes (tenant_id, parent_node_id);
CREATE INDEX IF NOT EXISTS idx_social_genome_nodes_kind
    ON social_genome_nodes (tenant_id, node_kind, evidence_status);
CREATE INDEX IF NOT EXISTS idx_social_genome_nodes_keywords
    ON social_genome_nodes USING GIN (keywords);

CREATE TABLE IF NOT EXISTS social_genome_edges (
    edge_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_node_id UUID NOT NULL REFERENCES social_genome_nodes(node_id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES social_genome_nodes(node_id) ON DELETE CASCADE,
    edge_kind TEXT NOT NULL
        CHECK (edge_kind IN ('contains', 'intersects', 'related', 'competes', 'audience_overlap', 'content_overlap')),
    weight DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (weight >= 0 AND weight <= 1),
    evidence_count BIGINT NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0
        CHECK (confidence >= 0 AND confidence <= 1),
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, source_node_id, target_node_id, edge_kind)
);

CREATE INDEX IF NOT EXISTS idx_social_genome_edges_source
    ON social_genome_edges (tenant_id, source_node_id, edge_kind);
CREATE INDEX IF NOT EXISTS idx_social_genome_edges_target
    ON social_genome_edges (tenant_id, target_node_id, edge_kind);

CREATE TABLE IF NOT EXISTS social_genome_observations (
    observation_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    node_id UUID NOT NULL REFERENCES social_genome_nodes(node_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    engagement_rate DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (engagement_rate >= 0),
    viral_velocity DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (viral_velocity >= 0),
    sentiment_index DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (sentiment_index >= -1 AND sentiment_index <= 1),
    content_count BIGINT NOT NULL DEFAULT 1 CHECK (content_count > 0),
    evidence_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_social_genome_observations_node_time
    ON social_genome_observations (tenant_id, node_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_genome_observations_platform
    ON social_genome_observations (tenant_id, platform, observed_at DESC);

CREATE TABLE IF NOT EXISTS social_genome_sources (
    source_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    authority_score DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (authority_score >= 0 AND authority_score <= 1),
    freshness_weight DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (freshness_weight >= 0 AND freshness_weight <= 1),
    terms_uri TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_social_genome_sources_tenant
    ON social_genome_sources (tenant_id, enabled);

CREATE TABLE IF NOT EXISTS social_genome_scores (
    score_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    node_id UUID NOT NULL REFERENCES social_genome_nodes(node_id) ON DELETE CASCADE,
    demand_score DOUBLE PRECISION NOT NULL CHECK (demand_score >= 0 AND demand_score <= 1),
    engagement_score DOUBLE PRECISION NOT NULL CHECK (engagement_score >= 0 AND engagement_score <= 1),
    velocity_score DOUBLE PRECISION NOT NULL CHECK (velocity_score >= 0 AND velocity_score <= 1),
    evidence_score DOUBLE PRECISION NOT NULL CHECK (evidence_score >= 0 AND evidence_score <= 1),
    opportunity_score DOUBLE PRECISION NOT NULL CHECK (opportunity_score >= 0 AND opportunity_score <= 1),
    sample_size BIGINT NOT NULL CHECK (sample_size >= 0),
    method_version TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_social_genome_scores_rank
    ON social_genome_scores (tenant_id, opportunity_score DESC, computed_at DESC);
