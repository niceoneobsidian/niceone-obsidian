-- OIS Football Intelligence v1 persistence boundary.
-- These tables are append-oriented; model/evidence versions are immutable.

CREATE TABLE IF NOT EXISTS football_competitions (
    competition_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    season TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS football_teams (
    team_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    competition_id TEXT REFERENCES football_competitions(competition_id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS football_players (
    player_id TEXT PRIMARY KEY,
    team_id TEXT REFERENCES football_teams(team_id),
    name TEXT NOT NULL,
    position TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS football_fixtures (
    fixture_id TEXT PRIMARY KEY,
    competition_id TEXT REFERENCES football_competitions(competition_id),
    home_team_id TEXT NOT NULL REFERENCES football_teams(team_id),
    away_team_id TEXT NOT NULL REFERENCES football_teams(team_id),
    kickoff_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    source_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    content_hash TEXT,
    UNIQUE (home_team_id, away_team_id, kickoff_at)
);

CREATE TABLE IF NOT EXISTS football_team_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    fixture_id TEXT NOT NULL REFERENCES football_fixtures(fixture_id),
    team_id TEXT NOT NULL REFERENCES football_teams(team_id),
    observed_at TIMESTAMPTZ NOT NULL,
    elo DOUBLE PRECISION,
    attack_strength DOUBLE PRECISION,
    defense_strength DOUBLE PRECISION,
    xg_for DOUBLE PRECISION,
    xg_against DOUBLE PRECISION,
    recent_form DOUBLE PRECISION,
    rest_days DOUBLE PRECISION,
    squad_strength DOUBLE PRECISION,
    lineup_confidence DOUBLE PRECISION,
    injuries_impact DOUBLE PRECISION,
    shots_on_target_for DOUBLE PRECISION,
    shots_on_target_against DOUBLE PRECISION,
    possession DOUBLE PRECISION,
    source_id TEXT NOT NULL,
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS football_market_observations (
    market_observation_id BIGSERIAL PRIMARY KEY,
    fixture_id TEXT NOT NULL REFERENCES football_fixtures(fixture_id),
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    odds DOUBLE PRECISION NOT NULL CHECK (odds > 0),
    observed_at TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL,
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS football_predictions (
    prediction_id UUID PRIMARY KEY,
    fixture_id TEXT NOT NULL REFERENCES football_fixtures(fixture_id),
    created_at TIMESTAMPTZ NOT NULL,
    prediction_timestamp TIMESTAMPTZ NOT NULL,
    model_ensemble_version TEXT NOT NULL,
    feature_set_version TEXT NOT NULL,
    dataset_version TEXT,
    home_probability DOUBLE PRECISION NOT NULL CHECK (home_probability BETWEEN 0 AND 1),
    draw_probability DOUBLE PRECISION NOT NULL CHECK (draw_probability BETWEEN 0 AND 1),
    away_probability DOUBLE PRECISION NOT NULL CHECK (away_probability BETWEEN 0 AND 1),
    expected_home_goals DOUBLE PRECISION NOT NULL CHECK (expected_home_goals >= 0),
    expected_away_goals DOUBLE PRECISION NOT NULL CHECK (expected_away_goals >= 0),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    model_agreement DOUBLE PRECISION NOT NULL CHECK (model_agreement BETWEEN 0 AND 1),
    data_completeness DOUBLE PRECISION NOT NULL CHECK (data_completeness BETWEEN 0 AND 1),
    abstain BOOLEAN NOT NULL,
    abstention_reason TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    prediction_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS football_prediction_outcomes (
    outcome_id BIGSERIAL PRIMARY KEY,
    prediction_id UUID NOT NULL REFERENCES football_predictions(prediction_id),
    final_home_goals INTEGER,
    final_away_goals INTEGER,
    outcome TEXT,
    settled_at TIMESTAMPTZ,
    settlement_source_id TEXT,
    UNIQUE (prediction_id)
);

CREATE TABLE IF NOT EXISTS football_model_evaluations (
    evaluation_id UUID PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    evaluation_start TIMESTAMPTZ NOT NULL,
    evaluation_end TIMESTAMPTZ NOT NULL,
    sample_count INTEGER NOT NULL,
    brier_score DOUBLE PRECISION NOT NULL,
    log_loss DOUBLE PRECISION NOT NULL,
    accuracy DOUBLE PRECISION NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS football_model_promotions (
    promotion_id UUID PRIMARY KEY,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('TRAINED','EVALUATED','SHADOW','CANARY','PROMOTED','ROLLBACK')),
    evaluation_id UUID REFERENCES football_model_evaluations(evaluation_id),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_football_predictions_fixture_time ON football_predictions(fixture_id, prediction_timestamp);
CREATE INDEX IF NOT EXISTS idx_football_market_fixture_time ON football_market_observations(fixture_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_football_evaluations_model ON football_model_evaluations(model_id, model_version);
