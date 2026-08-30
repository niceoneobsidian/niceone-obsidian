# OIS Football Intelligence v2

## Purpose

Upgrade the initial deterministic football domain into a governed probabilistic intelligence foundation without weakening the OIS execution boundary.

## Pipeline

```text
Licensed / public evidence
        ↓
Entity resolution + provenance
        ↓
Leakage-safe pre-match feature vector
        ↓
Elo + Poisson + Dixon-Coles baselines
        ↓
Optional market prior
        ↓
Ensemble probability
        ↓
10,000+ seeded Monte Carlo simulations
        ↓
Confidence / agreement / completeness
        ↓
Abstain when evidence is weak
        ↓
Audit record
        ↓
Walk-forward evaluation + calibration
        ↓
Champion / challenger promotion through OIS governance
```

## Intelligence layers

### Data plane
Historical match results should eventually cover multiple seasons and leagues. The production data adapter must retain source identity, observation time, content hash, entity mapping, and licensing/provenance metadata. Real-time adapters should add confirmed lineups, injuries, tactical formations, referee context, weather and market observations without mixing future information into historical training rows.

### Feature plane
`features.py` converts a pre-match `MatchState` into stable numeric features including Elo gap, attack/defence gap, xG gap, form, rest, squad/injury effects, shots on target, possession, tactical/referee/weather/travel context, market gap and market movement.

Feature generation must remain point-in-time correct. A training row may only use information available at that row's prediction timestamp.

### Model plane
The current ensemble contains dependency-light reference models. XGBoost/CatBoost/LightGBM and temporal models should be added only behind the same `ModelProbability` contract and promoted through out-of-sample evaluation. Learned weights must be evidence-derived rather than permanently hard-coded.

### Simulation plane
Monte Carlo translates expected goals into an empirical score/outcome distribution. A supplied seed makes a run reproducible for audit. Simulation does not manufacture predictive information; its quality is bounded by the quality and calibration of the underlying goal-rate estimates.

### Calibration plane
Evaluate multiclass probabilities with Brier score, log loss and accuracy. Reliability bins are available for calibration analysis. The target should be defined per league, season, horizon and regime after establishing a historical benchmark; `0.18–0.20` is not a universal guarantee or acceptance criterion.

### Governance plane
No model is promoted because it looks accurate on one test set. The intended lifecycle is:

```text
TRAINED → EVALUATED → SHADOW → CANARY → PROMOTED
                           ↓
                        ROLLBACK
```

All promotions must retain model version, feature-set version, dataset version, evaluation period, metrics, provenance and approval evidence.

## 98% accuracy target

98% should remain a research target for a narrowly defined prediction regime, not a universal system promise. Football outcomes contain substantial irreducible uncertainty. OIS should optimize calibrated probabilities, proper scoring rules, robustness and decision usefulness rather than overfit to a headline accuracy number.

## Next implementation gates

1. Build licensed/API-Football/FBref-compatible adapters with provenance contracts.
2. Implement canonical team/player/competition entity resolution.
3. Build immutable historical datasets and point-in-time feature snapshots.
4. Add walk-forward backtesting by league and season.
5. Add fitted Dixon-Coles and gradient-boosted models.
6. Add player/lineup/injury/tactical intelligence.
7. Add live-state updating and event ingestion.
8. Add drift monitoring and champion/challenger promotion.
9. Integrate model registry, evidence ledger and OIS measurement/learning.
10. Publish only after runtime and evaluation gates pass.
