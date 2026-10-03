# Evidence Runtime v1 — Football Replay Vertical Slice

## Status

Implemented on branch `feat/evidence-runtime-v1-football-replay`.

The vertical slice is connected to the public StatsBomb Open Data repository through a provider adapter. A multi-match benchmark contract is now integrated on top of the same governed replay path. The implementation remains replay-only and deterministic; it does not claim production live-data readiness.

## Runtime boundary

```text
StatsBomb Open Data
        |
        | immutable historical source
        v
Football Provider Adapter
  - normalize match
  - derive pre-match features only
  - retain source lineage
        |
        v
Football Intelligence
        |
        | proposal: football.replay.predict
        v
Evidence Runtime v1
  ingest observation
        |
  admissibility
  - evidence exists
  - evidence freshness
  - authorization-root binding
  - policy snapshot
        |
  single-use authorization
        |
  deterministic executor
        |
  execution receipt
        |
  outcome verification
        |
  measurement
        |
  append-only hash-chain ledger
        |
        v
Football Replay Benchmark
  - corpus selection
  - chronological ordering
  - pre-match history gate
  - dataset digest
  - accuracy / Brier / log-loss
  - evaluated / skipped / failed counts
```

The implementation follows the repository's existing separation between platform runtime and domain logic. Football Intelligence remains a domain provider of deterministic prediction; the runtime owns authority, evidence and execution boundaries.

## Implemented contracts

- `EvidenceEnvelope`: content-addressed observation identity with provenance and parent references.
- `EvidenceLedgerV1`: append-only hash-chain evidence record with verification.
- `AdmissibilityDecision`: deterministic allow/deny decision with action, evidence and policy digests.
- `SingleUseAuthorization`: short-lived, digest-bound execution authority.
- `ExecutionReceipt`: records the governed execution and output digest.
- `OutcomeReceipt`: records deterministic outcome verification.
- `StatsBombOpenDataProvider`: public JSON adapter with injectable transport for deterministic tests.
- `StatsBombReplayInput`: normalized match, outcome, source identity and source lineage.
- `FootballReplayBenchmark`: multi-match corpus runner using the same governed replay path.
- `FootballBenchmarkResult`: immutable benchmark result containing dataset digest, coverage and prediction metrics.

## Football replay paths

### Fixture path

`FootballReplay.run()` executes:

1. ingest historical match-state evidence;
2. ingest historical outcome evidence;
3. create a structured prediction action;
4. verify that action is present in the authorization root;
5. evaluate evidence freshness and policy;
6. mint single-use authorization;
7. execute the existing `football_intelligence.predict_match` capability;
8. record an execution receipt;
9. verify the replay outcome;
10. run the existing leakage-safe football evaluation;
11. append measurement evidence to the ledger.

### Real-data path

`FootballReplay.run_statsbomb()` executes the same runtime path, but first:

1. retrieves the selected competition/season match JSON from StatsBomb Open Data;
2. identifies the target match;
3. filters historical matches strictly before kickoff;
4. derives recent form, goals, attack/defence and Elo-like pre-match features;
5. excludes post-match records from feature construction;
6. preserves the target match plus pre-match history as source evidence;
7. passes the normalized `MatchState` through the exact same admissibility and authorization boundary.

This prevents a replay from using the final result to construct the prediction state.

## Benchmark path

`FootballReplayBenchmark.run()` adds the first corpus-level integration layer:

1. fetches one competition/season corpus;
2. sorts fixtures chronologically;
3. optionally selects an explicit match-id set and limit;
4. requires a configurable amount of pre-match history before evaluation;
5. routes every eligible fixture through `FootballReplay.run_statsbomb()`;
6. records evaluated, skipped and failed cases separately;
7. computes accuracy, multiclass Brier score and log-loss only from completed predictions;
8. produces a SHA-256 digest of the source corpus for dataset identity.

The benchmark is deliberately a measurement boundary, not a promotion decision. Promotion thresholds, calibration policy and model-version comparison should be added only after the benchmark is exercised against a sufficiently large pinned corpus.

## Security invariants covered by tests

- External observations cannot expand the authorization root.
- Stale evidence is denied.
- Authorization is bound to exact action and evidence digests.
- Authorization cannot be replayed.
- Ledger tampering breaks verification.
- Football replay produces execution, outcome and measurement evidence.
- StatsBomb normalization uses only pre-kickoff records for prediction features.
- Source lineage explicitly records the pre-match feature cutoff and post-match exclusion.
- Benchmark selection and coverage are deterministic.
- Benchmark results retain a dataset digest.

## Data source

StatsBomb publishes selected historical football competitions as JSON, including competitions, matches, events, lineups and selected 360 data. The open-data repository requires attribution when publishing research or analysis based on the data. OIS should preserve the source identity and URI in evidence provenance.

Public source: https://github.com/hudl/open-data

## Remaining boundary

The real-data adapter and first benchmark contract are implemented, but promotion-grade football readiness still requires:

- execution of a real 100–500+ match benchmark;
- stronger team-state feature engineering;
- provider-data quality validation;
- pinned source commit/version rather than a moving `master` URL;
- persistent raw-data caching/object storage;
- multi-season and cross-competition evaluation;
- calibration and abstention analysis;
- runtime/telemetry integration for benchmark traces and failure attribution;
- explicit promotion thresholds and rollback evidence;
- live-feed adapter and operational freshness checks.

OpenTelemetry provides standardized semantic conventions for traces, metrics and logs, which is a suitable observability foundation for the next measurement layer.
