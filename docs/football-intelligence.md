# Football Intelligence F0-F12

## Status

This implementation adds the Football Intelligence origin layer to OIS. It is a governed domain, not a second kernel.

| Stage | Implementation | Promotion status |
|---|---|---|
| F0 Contract | canonical origin/lifecycle contracts | IMPLEMENTED |
| F1 Live fixture/result ingestion | Sportmonks v3 adapter | IMPLEMENTED / requires configured credential |
| F2 Historical database | SQLite development adapter; map to OIS PostgreSQL for production | IMPLEMENTED / integration boundary |
| F3 Team-strength model | chronological Elo + attack/defence state | IMPLEMENTED |
| F4 xG model | leakage-safe baseline xG/Poisson | IMPLEMENTED |
| F5 Probability calibration | validation-window temperature scaling | IMPLEMENTED |
| F6 Odds/market intelligence | no-vig implied probabilities + model edge | IMPLEMENTED |
| F7 Backtesting engine | chronological backtest | IMPLEMENTED |
| F8 Walk-forward evaluation | expanding-window evaluation | IMPLEMENTED |
| F9 OIS Evidence Ledger | hash-addressed evidence event boundary | IMPLEMENTED / OIS sink integration required |
| F10 Football Agent + Supervisor | governed routing; no direct side effects | IMPLEMENTED |
| F11 Live intelligence dashboard | read-only dashboard payload contract | IMPLEMENTED / UI integration required |
| F12 Controlled model evolution | evidence-backed reversible proposal | IMPLEMENTED / promotion requires OIS gate |

## Data boundary

Sportmonks currently documents fixture schedules/results, in-play livescores, xG, statistics and odds through its v3 Football API. The adapter normalizes only the fields required by OIS and preserves a source hash for provenance.

## Validation boundary

The system must not promote a model from code existence alone. F7/F8 metrics, calibration evidence, source provenance, security/observability/recovery evidence and rollback capability are required before production activation.

## Runtime

Set `SPORTMONKS_TOKEN` only in the runtime secret store. Never commit tokens. The development store defaults to `data/football_intelligence.db`; production persistence should use the existing OIS PostgreSQL/evidence services.
