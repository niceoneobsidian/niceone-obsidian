# Evidence Lifecycle

ODI uses explicit evidence states to prevent architecture from being mistaken for operational capability.

```text
UNKNOWN
  ↓
DESIGNED
  ↓
IMPLEMENTED
  ↓
TESTED
  ↓
INTEGRATED
  ↓
DEPLOYED
  ↓
ACTIVATED
  ↓
PRODUCTION VERIFIED
```

A capability may move forward only when the evidence appropriate to its risk and lifecycle state exists.

## Production Verification Signals

Depending on capability risk, evidence may include:

- implementation evidence
- unit and contract tests
- integration tests
- runtime traces
- security checks
- visual validation
- performance measurements
- deployment evidence
- rollback evidence
- operational verification

Documentation alone never upgrades lifecycle state.
