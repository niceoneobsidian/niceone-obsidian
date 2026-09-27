# Football Market Intelligence

Football Market Intelligence is the market-domain layer above `football_intelligence`.

## Responsibility

```text
MATCH INTELLIGENCE
      ↓
PREDICTION
      ↓
MARKET TRANSLATION
      ↓
MARKET EVENT
      ↓
OUTCOME OBSERVATION
      ↓
MARKET EVALUATION
      ↓
ATTRIBUTION
      ↓
BACKTEST / LEARNING
```

The domain owns market semantics and deterministic settlement/evaluation primitives. OIS platform services remain authoritative for execution, policy, durable persistence, observability, approval and model/workflow promotion.

## Canonical unit

`MarketEvent` is the atomic unit. An accumulator is a derived portfolio of market events and should not replace the atomic event ledger.

Each event preserves `match_id`, `prediction_id`, prediction version, odds, implied probability, model probability, confidence and evidence so performance can be attributed to the upstream prediction lineage.

## Supported reference markets

- Result: home / draw / away
- Double chance: 1X / X2 / 12
- Total goals: over / under
- Team goals: home/away over / under
- Both teams to score: yes / no
- Handicap: home / away
- Special: OIS reference `1UP` semantics

Bookmaker-specific settlement rules must be implemented by an explicit licensed adapter. The core domain must not infer proprietary early-payout semantics.

## Learning boundary

Observed outcomes are evaluation data, not permission to alter production models. Backtesting, attribution, champion/challenger comparison and promotion remain governed OIS workflows.
