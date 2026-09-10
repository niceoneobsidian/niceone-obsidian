# Football Statistics Data Plane v1

## Purpose

Provide OIS with normalized match and player evidence for football prediction and market analysis without coupling the domain to a vendor-specific schema.

## Providers

### API-Football

Environment variable:

`API_FOOTBALL_KEY`

Implemented calls:

- `/fixtures?id={fixture_id}` — match identity/status/result context.
- `/fixtures/statistics?fixture={fixture_id}` — team match statistics.
- `/fixtures/players?fixture={fixture_id}` — player match performance.

API-Football documents live fixtures, match statistics and player-performance endpoints; live fixture data is updated frequently, so polling frequency must remain a runtime policy rather than being embedded in the domain.

### Sportmonks

Environment variable:

`SPORTMONKS_API_TOKEN`

Implemented fixture request with:

`include=stats;lineups.details`

Sportmonks documents `stats` for fixture statistics and `lineups.details` for player-level fixture statistics.

## Architecture

```text
Provider API
    ↓
Credentialed adapter
    ↓
Canonical MatchFeed
    ├── MatchStatistics
    └── PlayerMatchStatistics
    ↓
Prediction-time feature builder
    ↓
FootballPrediction / MarketSignal
```

The domain never stores API credentials. HTTP transport is injectable, allowing OIS execution policy to control retries, rate limits, caching, persistence and observability.

## Betting features

The initial feature layer exposes:

- shots
- shots on target
- corners
- possession
- cards
- xG when supplied by the provider
- player minutes
- player rating
- player shots / shots on target
- goals / assists
- key passes
- tackles / interceptions
- duels
- successful dribbles
- fouls
- cards

Feature builders accept an `as_of` timestamp and discard later observations. This prevents future player/match statistics from entering prediction-time datasets.

## Evidence boundary

These features are inputs, not proof of predictive value. Model calibration, backtesting, attribution and promotion remain separate OIS controls. Live wager execution is not part of this layer.
