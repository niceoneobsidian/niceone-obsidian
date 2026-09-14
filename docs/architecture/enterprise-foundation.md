# Enterprise Architecture Foundation

This document records the enforceable foundation added for the OIS modular monolith.

## Dependency direction

```text
interfaces -> application -> domain
infrastructure -> application ports
application and domain do not import provider SDKs, database clients, or transport adapters
```

The `ois.contracts` package contains stable cross-boundary models. API DTOs, persistence models, and provider responses must be mapped to these contracts rather than passed through the system as untyped dictionaries.

## Mandatory authorization

Every side-effecting operation must accept an `ExecutionRequest`. The request carries a matching, non-expired `AuthorizationDecision`, capability version, principal, deadline, and idempotency key. Executors must call `assert_authorized()` before performing the side effect. Deny, mismatch, expiry, and deadline violations fail closed.

## Lifecycle state machine

Execution transitions are declared in `ois.application.state`. Invalid transitions are rejected. Retries, rollback, and escalation are explicit states and must be independently authorized by the application service.

## Persistence ports

`EvidenceRepository` and `ExecutionStateRepository` are protocols. PostgreSQL, Redis, and other adapters implement these ports; application code must not depend on their clients. Evidence is append-oriented and separate from logs, metrics, and traces.

## Versioning

- Application version: package metadata
- Contract version: `ois.contracts.CONTRACT_VERSION`
- Evidence schema version: `EvidenceRecord.contract_version`
- Persistence schema version: owned by migrations in the selected adapter

A contract change requires a new contract version, compatibility tests, and migration notes.

## Implementation evidence

The architecture CI job executes the contract and state-machine tests on every pull request. Future adapters must add integration tests proving authorization cannot be bypassed and that state transitions are persisted transactionally.
