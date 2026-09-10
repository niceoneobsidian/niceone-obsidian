# Football Market Intelligence

Football Market Intelligence is the market-domain layer above `football_intelligence`.

## Responsibility

```text
MATCH INTELLIGENCE
      ↓
WEB DATA PLANE
      ↓
CANONICAL MARKET CATALOG
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

## Web Data Plane v1

Provider adapters are deliberately isolated from the kernel and use injected transport callables. Current adapters:

- `football-data.org` v4 for fixtures, statuses and results.
- `The Odds API` for bookmaker odds and historical snapshots.
- `Sportmonks` for bookmaker odds, market metadata and bookmaker update timestamps.

The normalized observation layer preserves provider identity, provider market key, market description, canonical market key, bookmaker, line, decimal odds, implied probability, observation timestamp, source timestamp and payload hash.

Prediction-time consumers fail closed on source evidence dated after the prediction timestamp. Raw provider payloads are represented by provenance hashes rather than silently becoming mutable model state.

## Canonical market catalog

The catalog is broader than the deterministic settlement families so the engine can ingest modern sportsbook feeds without changing its schema for every provider-specific market.

### Match/result markets

- 1X2 / Match Result
- Double Chance
- Draw No Bet
- European Handicap
- Asian Handicap
- Total Goals Over/Under
- Team Total Goals
- Both Teams To Score / GG-NG
- Correct Score
- Exact Goals
- 1st Half Result
- Half Time / Full Time
- Rest of Match
- To Qualify
- Outrights / Futures

### Match-statistic markets

- Corners Over/Under
- Corners 1X2
- Team Corners
- Cards / Bookings
- Booking Points
- Free Kicks
- Offsides
- Penalties

### Player markets

- Goalscorer / Anytime / First / Last
- Player Goals
- Player Assists
- Player Shots
- Player Shots on Target
- Player Passes
- Player Tackles
- Player Cards
- Next Goalscorer

### Live/event markets

- Next Goal
- Next Scoring Type
- Rest of Match
- Period-specific variants
- Combination / Bet Builder
- Special / Novelty markets

This is a **canonical taxonomy**, not a claim that every bookmaker offers every market. Actual bookmaker availability is derived from observed feed data through `build_market_coverage()`.

## Provider normalization

Known provider mappings currently include SportyBet market IDs exposed by the researched feed and The Odds API market keys. Unknown provider-specific markets are preserved as raw provider keys and are not fabricated into a canonical market.

For example, the SportyBet feed exposes 1X2, Over/Under, Double Chance, Draw No Bet, Handicap, Asian Handicap, GG/NG, Correct Score, Half Time/Full Time, first-half variants and team totals. The canonical mapper preserves these as stable engine keys.

## Coverage model

`BookmakerMarketCoverage` reports the markets actually observed for a bookmaker/provider pair, including:

- unique match count
- observation count
- canonical market keys
- first observation timestamp
- latest observation timestamp

This enables the engine to answer `what markets does this feed actually provide?` rather than relying on a static marketing list.

## Settlement boundary

Bookmaker-specific settlement rules must be implemented by an explicit licensed adapter. The core domain must not infer proprietary early-payout semantics such as special `1UP` treatment merely from a generic handicap/result market.

## Learning boundary

Observed outcomes are evaluation data, not permission to alter production models. Backtesting, attribution, champion/challenger comparison and promotion remain governed OIS workflows.
