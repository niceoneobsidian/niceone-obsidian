# Football Market Intelligence

Football Market Intelligence is the market-domain layer above `football_intelligence`.

## Responsibility

```text
RAW PROVIDER FEEDS
      ↓
ENTITY RESOLUTION
      ↓
APPEND-ONLY FEATURE STORE
      ↓
PREDICTION-TIME FEATURE BUILDER
      ↓
┌───────────────────────────────────┐
│ Goal       → O/U, BTTS, team goals│
│ Result     → 1X2, DNB, double     │
│ Corner     → O/U, handicaps        │
│ Card       → O/U, player cards    │
│ Shot       → player shots / SOT   │
│ PlayerGoal → anytime scorer       │
│ LiveState  → live totals / next  │
└───────────────────────────────────┘
      ↓
CALIBRATION
      ↓
MARKET PROBABILITY
      ↓
FAIR ODDS
      ↓
BOOKMAKER PRICE COMPARISON
      ↓
EDGE / EV
      ↓
WALK-FORWARD BACKTEST
      ↓
ABSTAIN / PUBLISH
      ↓
OUTCOME OBSERVATION
      ↓
MARKET EVALUATION / ATTRIBUTION
```

The domain owns market semantics and deterministic reference modelling, pricing and evaluation primitives. OIS platform services remain authoritative for execution, policy, durable persistence, observability, approval and model/workflow promotion.

## Market-specific modelling

`models.py` deliberately keeps each market family independent. Goal and result probabilities share a scoreline distribution, while corners/cards use count models, player shots use exposure-adjusted count models, player goals use a scoring hazard, and live markets condition on elapsed time and current score.

These are **reference probability engines**, not claims of predictive superiority. Production parameters must be fitted from historical provider data and promoted only after governed out-of-sample validation.

## Feature and pricing pipeline

`pipeline.py` provides:

- provider observation provenance and payload hashing;
- deterministic entity alias resolution;
- append-only feature snapshots with prediction-time filtering;
- market feature requests that reject missing history;
- best-available bookmaker price selection;
- calibration-aware market quotes;
- edge and expected-value calculations;
- explicit abstention when evidence, calibration or price gates fail;
- chronological walk-forward evaluation primitives.

## Canonical unit

`MarketEvent` remains the atomic market ledger unit. An accumulator is a derived portfolio of market events and must not replace the atomic event ledger.

Each event preserves `match_id`, `prediction_id`, prediction version, odds, implied probability, model probability, confidence and evidence so performance can be attributed to the upstream prediction lineage.

## Supported reference markets

- Result: home / draw / away
- Double chance: 1X / X2 / 12
- Total goals: over / under
- Team goals: home/away over / under
- Both teams to score: yes / no
- Handicap: home / away
- Corners and cards totals
- Player shots and shots on target
- Anytime scorer
- Live totals and next-goal state
- Special: OIS reference `1UP` semantics

Bookmaker-specific settlement rules must be implemented by an explicit licensed adapter. The core domain must not infer proprietary early-payout semantics.

## Learning boundary

Observed outcomes are evaluation data, not permission to alter production models. Backtesting, calibration, attribution, champion/challenger comparison and promotion remain governed OIS workflows.
