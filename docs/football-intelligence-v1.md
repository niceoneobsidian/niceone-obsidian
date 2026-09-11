# Football Intelligence Engine v1 — OIS Implementation Specification

Status: IMPLEMENTATION CANDIDATE — Gate 1 code added on `feat/football-intelligence-v1-implementation`.

## 1. Boundary

Football Intelligence is a domain capability inside OIS. It does not create a parallel Kernel, registry, policy engine, or execution runtime. The OIS Kernel remains the governed execution boundary; the domain supplies contracts, model implementations, agents/capabilities and workflows.

Source-derived architecture requires the separation of Capability Registry, Agent Registry, Tool Registry, Workflow Registry, Model Registry, Policy, Validation, Recovery and Evidence. The repository already has the Kernel contracts and the football domain manifest.

## 2. v1 objective

Produce auditable pre-match football probability distributions and simulation outputs from point-in-time evidence, with explicit abstention, calibration and later promotion gates.

Primary flow:

```text
Football Request
  -> Intent / Policy
  -> football.data_agent
  -> Entity + provenance normalization
  -> football.team_agent / football.player_agent
  -> leakage-safe features
  -> Elo + Poisson + Dixon-Coles
  -> optional market prior
  -> calibrated ensemble
  -> Monte Carlo simulation
  -> confidence / agreement / completeness
  -> abstain or publish candidate prediction
  -> prediction ledger
  -> outcome settlement
  -> calibration / backtest
  -> champion/challenger promotion
```

## 3. Exact OIS capabilities

| Capability | Input | Output | Side effect | Gate |
|---|---|---|---|---|
| `football.ingest` | `FootballDataBatch` | normalized batch | no | P0 |
| `football.team_state` | `MatchHistory` | `TeamSnapshot` | no | P0 |
| `football.player_state` | `PlayerDataBatch` | `PlayerState` | no | P1 |
| `football.features` | `MatchState` | `FeatureVector` | no | P0 |
| `football.predict_1x2` | `MatchState` | `FootballPrediction` | no | P0 |
| `football.simulate` | `MatchState` | `SimulationResult` | no | P0 |
| `football.tactical_analysis` | `MatchState` | `TacticalAnalysis` | no | P1 |
| `football.live_update` | `LiveMatchState` | `FootballPrediction` | no | P2 |
| `football.calibrate` | `PredictionSet` | `CalibrationReport` | no | P0 |
| `football.backtest` | `DatasetSpec` | `BacktestReport` | no | P0 |
| `football.abstain` | `FootballPrediction` | `AbstentionDecision` | no | P0 |
| `football.research` | `FootballResearchQuery` | `FootballResearchBrief` | no | P1 |

## 4. Agent Registry entries

- `football.data_agent` — ingestion and validation.
- `football.team_agent` — team strength and features.
- `football.player_agent` — player/lineup state.
- `football.tactical_agent` — tactical matchup.
- `football.prediction_agent` — model federation and simulation.
- `football.live_agent` — live state updates.
- `football.evaluation_agent` — calibration and walk-forward evaluation.
- `football.supervisor` — supervised football workflow delegation.

Agents request capabilities; they do not receive direct unrestricted side-effect authority.

## 5. Tool Registry entries

- `football.data.api` — fixtures, results, teams, match statistics.
- `football.data.live` — live events and match state.
- `football.data.odds` — timestamped odds/market observations.
- `football.data.web` — public research retrieval with provenance.
- `football.data.fbref` — historical statistics where permitted/licensed.

Every tool must ultimately conform to the existing OIS `ToolContract`, including identity/version, schemas, permissions, risk, side effects, timeout, retry, idempotency, validation and evidence.

## 6. Model Registry entries

| Model ID | Type | v1 state | Contract |
|---|---|---|---|
| `football.elo.v1` | statistical | reference | `ModelProbability` |
| `football.poisson.v1` | statistical | reference | `ModelProbability` |
| `football.dixon_coles.v1` | statistical | reference | `ModelProbability` |
| `football.ensemble.v1` | ensemble | candidate | `FootballPrediction` |

ML models such as XGBoost/LightGBM/CatBoost and temporal models are v1+ candidates only after they implement the same probability contract and pass out-of-sample evaluation.

## 7. Canonical data schemas

The code-level contracts are in `ois/domains/football_intelligence/schemas.py`:

- `FootballEvidence`: source ID, URI, observation time, confidence, source type and content hash.
- `TeamSnapshot`: Elo, attack/defence strength, home advantage, form, xG/xGA, rest, squad/lineup, injury impact, shots on target and possession.
- `MatchState`: fixture identity, competition, kickoff, team snapshots, referee/weather/tactical/travel factors, current/prior market observations and evidence.
- `ModelProbability`: normalized 1X2 probabilities plus expected goals.
- `SimulationResult`: iterations, 1X2 frequencies, empirical expected goals, most likely score, scoreline distribution and seed.
- `FootballPrediction`: probabilities, expected goals, confidence, model agreement, data completeness, abstention state, model outputs, simulation and evidence.

All Pydantic models forbid unknown fields so connector drift fails at the contract boundary.

## 8. Feature contract

`build_feature_vector()` is point-in-time only. v1 features include:

- Elo gap
- attack/defence gaps
- xG gap
- form gap
- rest gap
- squad/injury gaps
- shots-on-target gap
- possession gap
- home advantage
- referee/weather/tactical/travel factors
- market gap and market movement
- lineup-confidence gap

Historical training rows MUST use only information available at their prediction timestamp.

## 9. Statistical engine

v1 uses three deterministic reference models:

1. Elo — team-strength probability baseline.
2. Poisson — expected-goals scoring distribution.
3. Dixon-Coles reference correction — conservative low-score/draw adjustment.

`football.ensemble.v1` federates them, optionally blends a market prior, calculates agreement/completeness/evidence quality and abstains when the configured gate is not met.

The hard-coded weights are reference weights, not learned claims. Promotion of learned weights requires evaluation evidence.

## 10. Simulation

The simulation layer uses seeded Monte Carlo with a conservative shared-goal component. Default is 10,000 iterations. A seed makes a run reproducible. Simulation is not treated as new predictive information; its quality remains bounded by the input goal-rate model.

## 11. Validation metrics

v1 exposes:

- multiclass Brier score
- multiclass log loss
- accuracy
- reliability bins

Promotion should optimize calibrated probabilities and decision usefulness, not a universal accuracy promise.

## 12. Workflows

### `football.predict.v1`

```text
INTAKE
 -> NORMALIZE
 -> POLICY
 -> DATA
 -> FEATURES
 -> MODEL_ENSEMBLE
 -> SIMULATE
 -> ABSTAIN_GATE
 -> VALIDATE
 -> CHECKPOINT
 -> EVIDENCE
```

### `football.backtest.v1`

```text
DATASET_SNAPSHOT
 -> POINT_IN_TIME_FEATURES
 -> WALK_FORWARD_SPLIT
 -> MODEL_RUN
 -> SETTLE_OUTCOMES
 -> BRIER / LOGLOSS / ACCURACY
 -> CALIBRATION
 -> EVIDENCE
```

### `football.live_prediction.v1` (P2)

```text
LIVE_EVENT
 -> STATE_RECONSTRUCTION
 -> LIVE_FEATURES
 -> LIVE_MODEL
 -> VALIDATE
 -> CHECKPOINT
 -> EVIDENCE
```

## 13. Database tables

Migration: `infrastructure/postgres/football_intelligence_v1.sql`.

- `football_competitions`
- `football_teams`
- `football_players`
- `football_fixtures`
- `football_team_snapshots`
- `football_market_observations`
- `football_predictions`
- `football_prediction_outcomes`
- `football_model_evaluations`
- `football_model_promotions`

Prediction/evaluation records are append-oriented. Model and dataset versions are immutable references. Evidence and provenance are retained with prediction records.

## 14. API contract

The API belongs to the OIS Control Plane/API boundary; v1 domain handlers should expose these logical operations rather than bypassing policy:

- `POST /v1/football/predictions` — submit a governed pre-match prediction request.
- `GET /v1/football/predictions/{prediction_id}` — retrieve an auditable prediction.
- `POST /v1/football/simulations` — run a deterministic seeded simulation.
- `POST /v1/football/backtests` — submit an authorized evaluation job.
- `GET /v1/football/models` — list registered football models and lifecycle state.
- `GET /v1/football/fixtures/{fixture_id}` — retrieve canonical fixture state.
- `POST /v1/football/live/{fixture_id}/update` — P2 live update operation.

All endpoints must pass through OIS authentication, authorization, validation, execution, evidence and observability. This document does not claim those HTTP routes are already wired in the repository.

## 15. Repository structure

```text
ois/domains/football_intelligence/
  __init__.py
  schemas.py
  models.py
  features.py
  simulation.py
  calibration.py
  ensemble.py
  registry.py
  integration.py

ois/domains/football_market_intelligence/
  ... existing market domain ...

infrastructure/postgres/
  football_intelligence_v1.sql

docs/
  football-intelligence-v1.md

tests/football_intelligence/
  test_models.py
  test_ensemble.py
  test_v1_gates.py
```

## 16. Incremental validation gates

### Gate F0 — Architecture/contract

Pass when capability, agent, tool, model and workflow IDs match this specification and Pydantic contracts reject malformed input.

### Gate F1 — Deterministic statistical core

Pass when Elo, Poisson and Dixon-Coles probabilities normalize; feature generation is deterministic; seeded simulation is reproducible; ensemble output is auditable; calibration metrics are deterministic.

### Gate F2 — Data plane

Pass only after real adapters, provenance, timestamps, entity resolution and point-in-time snapshots are demonstrated.

### Gate F3 — Evaluation

Pass only after walk-forward backtests, Brier/log-loss/calibration reports and leakage tests pass on an immutable dataset version.

### Gate F4 — OIS runtime integration

Pass only after Control Plane → Supervisor → Planner → Kernel → football capability → validation → checkpoint → evidence is demonstrated end-to-end.

### Gate F5 — Production promotion

Pass only after security, observability, recovery, idempotency, deployment and outcome evidence pass. Model lifecycle is `TRAINED → EVALUATED → SHADOW → CANARY → PROMOTED`, with rollback.

## 17. Explicit non-goals for v1

- No universal 98% accuracy claim.
- No direct LLM-to-tool execution.
- No autonomous model promotion.
- No unproven live-feed claims.
- No copying external repositories as applications.
- No second OIS registry or second Kernel.

## 18. Evidence state

Current branch status must be reported as `IMPLEMENTED / TESTS-ADDED / RUNTIME-UNVERIFIED` until CI and the OIS runtime execute the new paths. A green source diff is not sufficient evidence of production readiness.
