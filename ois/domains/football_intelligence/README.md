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

## Planned production layers

1. Licensed historical/live data adapters with provenance.
2. Leakage-safe feature store and entity resolution.
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
