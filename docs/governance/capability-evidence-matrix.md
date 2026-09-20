# Capability evidence matrix

This matrix separates architectural intent from verified capability. Mark a capability as production verified only when the required evidence exists.

| Capability | Design | Implemented | Unit tested | Integrated | Runtime evidence | Deployment evidence | Rollback evidence | Status | Owner/issue |
|---|---|---|---|---|---|---|---|---|---|
| Authorization and policy enforcement | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Capability registry and version checks | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Durable execution persistence | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Idempotency and duplicate delivery | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Valid state transitions | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Append-only execution evidence | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Validation and outcome recording | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Bounded retry and recovery | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Rollback and escalation | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Health and readiness | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |
| Metrics, traces, and auditability | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | Unknown | |

## Evidence rules

- A passing unit test does not imply integration or production readiness.
- Runtime evidence must identify the exact commit and environment.
- Deployment evidence must include health, readiness, observability, and rollback verification.
- Security-sensitive capabilities require negative tests and least-privilege review.
- Update this matrix in the same pull request that changes capability claims.
