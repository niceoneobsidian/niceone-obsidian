# OIS Football Intelligence

Football Intelligence is an OIS domain, not a second application or second kernel.

## Architecture

The domain supplies canonical contracts, deterministic reference models, model federation,
confidence/abstention and evaluation primitives. The OIS kernel/control plane remain the
authoritative owners of execution, policy, permissions, persistence, observability and
promotion/rollback.

## Current implementation

- Canonical match/team/evidence/prediction schemas.
- Elo, Poisson and reference Dixon-Coles probability models.
- Deterministic ensemble with model-agreement and data-completeness signals.
- Explicit prediction abstention.
- Auditable prediction serialization.
- Multiclass Brier score, log loss and accuracy evaluation.
- Declarative capability/agent/workflow manifest.
- Provider-neutral live feed contracts with hashed evidence provenance.
- API-Football v3 adapter for live fixtures, team statistics and player statistics.
- Sportmonks v3 adapter for live scores plus fixture statistics and lineup/player details.
- StatsBomb Open Data adapter for historical event-level model training.
- Multi-provider reconciliation service for live match identity and prediction-time feature snapshots.

## Feed strategy

```text
                 OIS Football Data Plane
                          |
          +---------------+----------------+
          |               |                |
      API-Football    Sportmonks       StatsBomb
       live/basic      live/deep       historical
          |               |                |
          +---------------+----------------+
                          |
                 Canonical evidence
                          |
                 Feature snapshot
                          |
                 Football models
                          |
                 Market intelligence
```

API-Football is the low-friction live baseline. Sportmonks is the richer football feed
for deeper fixture/player/statistics coverage. StatsBomb Open Data is isolated to historical
event-level research and model training; it is not treated as a live source.

Credentials are runtime configuration only:

- `API_FOOTBALL_KEY`
- `SPORTMONKS_API_TOKEN`

No provider secret belongs in source control.

## Prediction-time safety

Provider observations carry an observation timestamp and deterministic payload hash. Feed
adapters normalize data before it reaches models. The feature service does not mutate model
state or place bets. Future information must be excluded by the downstream leakage-safe
feature/evaluation layer.

## Planned production layers

1. Licensed odds/bookmaker adapters with provenance and price snapshots.
2. Leakage-safe feature store and entity resolution across provider IDs.
3. Fitted league-specific statistical models.
4. XGBoost/LightGBM/CatBoost and temporal models behind the same contract.
5. Tactical, player, lineup, injury and market intelligence.
6. Monte Carlo score/state simulation.
7. Probability calibration and regime/drift detection.
8. Walk-forward backtesting and champion/challenger evaluation.
9. Shadow/canary promotion through existing OIS governance.
10. Live event updates only after pre-match validation is production-ready.

## Accuracy policy

98% is not a universal claim. It is a research target that may only be reported for a
predefined, statistically valid prediction regime with frozen evaluation rules, sufficient
coverage, temporal separation and calibrated probabilities. No future outcome may enter a
prediction feature or model-selection decision.
