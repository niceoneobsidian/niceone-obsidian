# Football Market Intelligence

Football Market Intelligence is the market-domain layer above `football_intelligence`.

## Responsibility

```text
API-Football / Sportmonks live + match/player statistics
                    │
StatsBomb Open Data historical events
                    ↓
RAW PROVIDER OBSERVATIONS + PAYLOAD HASH
                    ↓
ENTITY RESOLUTION
                    ↓
APPEND-ONLY FEATURE STORE
                    ↓
PREDICTION-TIME FEATURE BUILDER
                    ↓
┌──────────────────────────────────────┐
│ Goal       → O/U, BTTS, team goals   │
│ Result     → 1X2, DNB, double chance │
│ Corner     → O/U, handicaps           │
│ Card       → O/U, player cards       │
│ Shot       → player shots / SOT       │
│ PlayerGoal → anytime scorer           │
│ LiveState  → live totals / next goal  │
└──────────────────────────────────────┘
                    ↓
INDEPENDENT EMPIRICAL FITTING
                    ↓
CALIBRATION
                    ↓
MARKET PROBABILITY → FAIR ODDS → PRICE COMPARISON → EDGE / EV
                    ↓
WALK-FORWARD OOS VALIDATION
                    ↓
ABSTAIN / CANDIDATE / PUBLISH
```

The domain owns market semantics and deterministic modelling, pricing and evaluation primitives. OIS platform services remain authoritative for execution, policy, durable persistence, observability, approval and model/workflow promotion.

## Provider plane

The `football_intelligence` domain supplies the provider adapters used here:

- **API-Football** — live fixtures, fixture statistics and player statistics; credentials are runtime-only through `API_FOOTBALL_KEY`.
- **Sportmonks** — live scores, fixture statistics and lineup/player detail; credentials are runtime-only through `SPORTMONKS_API_TOKEN`.
- **StatsBomb Open Data** — historical competition/match/event archives for reproducible training; it is not treated as a live feed.

Provider observations carry timestamps, payload hashes and evidence identifiers. Live snapshots are appended to the market feature store through `provider_bridge.py` rather than being treated as immutable historical truth.

The provider integration follows the current public API contracts: API-Football fixtures are the master key for match events, lineups, statistics and player data; live fixture/event data is refreshed frequently; fixture statistics and player statistics are updated during live matches; and live odds must be captured in real time because the provider does not retain an in-play odds history. StatsBomb Open Data provides competitions, matches, events and lineups as JSON archives suitable for reproducible historical training.

## Empirical fitting

`historical.py` constructs chronological training rows. For each match, features are emitted **before** current-match events are applied to team/player history. Current-match events become labels only. This prevents outcome leakage.

`training.py` fits the seven families independently:

1. Goal — independent home/away Poisson rates.
2. Result — independent categorical likelihood for home/draw/away.
3. Corner — independent Poisson count rate.
4. Card — independent Poisson count rate.
5. Shot — independent player-shot/SOT count rates.
6. PlayerGoal — independent scoring hazard estimate.
7. LiveState — independent per-minute goal hazard.

These are empirical baselines, not a claim that all seven models are already calibrated or profitable. A model becomes eligible for promotion only after chronological out-of-sample evaluation and calibration. The research basis favors walk-forward evaluation and proper scoring rules such as log loss and Brier score over raw accuracy.

## Training entry point

`FootballModelTrainingService.fit_statsbomb_season(competition_id, season_id)` fetches a real StatsBomb historical season, builds leakage-safe rows and returns a **candidate** seven-model artifact. The service intentionally does not promote the artifact or mutate production model state.

`LiveFootballSnapshotCollector.collect()` polls the configured live provider service and appends prediction-time snapshots to the feature store. A scheduler/workflow should call this collector at the provider-appropriate cadence and let OIS policy/observability control retries, quotas and persistence.

## Canonical unit

`MarketEvent` remains the atomic market ledger unit. An accumulator is a derived portfolio of market events and must not replace the atomic event ledger.

Each event preserves `match_id`, `prediction_id`, prediction version, odds, implied probability, model probability, confidence and evidence so performance can be attributed to the upstream prediction lineage.

## Learning boundary

Observed outcomes are evaluation data, not permission to alter production models. Backtesting, calibration, attribution, champion/challenger comparison and promotion remain governed OIS workflows.
