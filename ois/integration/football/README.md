# Football Data Integration v1

Provider-neutral match and player-statistics ingestion for Football Intelligence and Market Intelligence.

## Providers

### Sportmonks

Set `SPORTMONKS_TOKEN`. The adapter uses the v3 Football API and requests related entities with `include`, allowing a fixture to carry participants, events, team statistics, lineups and per-player details in one response.

Useful operations:

- fixtures by date
- fixture enrichment
- player profiles
- player match statistics
- player season statistics

### API-Football / API-Sports

Set `API_FOOTBALL_KEY`. The adapter uses the API-Sports v3 Football API.

Useful operations:

- fixtures by date
- fixture enrichment
- player season statistics
- player match statistics

## OIS data flow

```text
Provider API
    -> provider adapter
    -> canonical FootballFixture / Player*Stat
    -> FootballDataGateway
    -> leakage-safe feature builder
    -> Football Intelligence
    -> Market Intelligence
    -> pricing / edge / CLV / backtest
```

The integration does not place wagers, call bookmaker execution endpoints, or bypass policy controls.

## Leakage rule

Only statistics known before a prediction timestamp should be passed to a predictive feature set. The adapter preserves provider identity and raw payloads so the ingestion layer can attach source timestamps and provenance before persistence.

## Production recommendation

Sportmonks is the preferred primary football data source because its current Football API documents fixtures, live scores, xG, team statistics and per-player match statistics in the same response shape. API-Football remains a useful secondary provider for redundancy and cross-source validation.
