# Evidence Runtime v1 — Football Replay Vertical Slice

## Status

Implemented on branch `feat/evidence-runtime-v1-football-replay`.

This is the first vertical implementation of the evidence-driven runtime. It is deliberately small and deterministic; it does not yet claim production live-data readiness.

## Runtime boundary

```text
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
```

The implementation follows the repository's existing separation between platform runtime and domain logic. Football Intelligence remains a domain provider of deterministic prediction; the runtime owns authority, evidence and execution boundaries.

## Implemented contracts

- `EvidenceEnvelope`: content-addressed observation identity with provenance and parent references.
- `EvidenceLedgerV1`: append-only hash-chain evidence record with verification.
- `AdmissibilityDecision`: deterministic allow/deny decision with action, evidence and policy digests.
- `SingleUseAuthorization`: short-lived, digest-bound execution authority.
- `ExecutionReceipt`: records the governed execution and output digest.
- `OutcomeReceipt`: records deterministic outcome verification.

## Football replay path

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

## Security invariants covered by tests

- External observations cannot expand the authorization root.
- Stale evidence is denied.
- Authorization is bound to exact action and evidence digests.
- Authorization cannot be replayed.
- Ledger tampering breaks verification.
- Football replay produces execution, outcome and measurement evidence.

## Known boundary

The current football replay test uses a deterministic fixture rather than a live provider. The next integration phase should replace or supplement the fixture adapter with immutable provider payloads (for example StatsBomb Open Data) and retain the same evidence and authorization boundary. StatsBomb publishes selected historical match events, lineups and competition data as open JSON research data. See the public repository: https://github.com/hudl/open-data
