# OCIF Governed Execution Boundary

**Status:** Candidate integration implementation. The branch now includes a PostgreSQL composition factory and PostgreSQL OCIF consumer integration test; deployment is not approved until CI, security, tenant-isolation and owner-review gates pass.

## Existing OIS control surfaces verified in source

- `ois/integration/spine.py`: `OISSpine.submit()` creates execution identity, checkpoints the request, calls the Kernel and returns execution status plus evidence events.
- `ois/kernel/runtime.py`: validates capability input, invokes the policy engine before execution, emits authorization evidence, checkpoints execution, supports idempotency and records recovery decisions.
- `ois/kernel/policy.py`: `DefaultPolicyEngine` evaluates tenant identity, required permissions, risk and irreversible side effects; denied authorization raises `AuthorizationDenied`.
- `ois/kernel/recovery.py`: `RecoveryPolicy` classifies failures and caps retry/recovery decisions. The `ocif.import.consume` capability retries known transient timeouts, connection failures, SQLite lock/busy errors and selected PostgreSQL transient lock/deadlock/serialization errors, with a hard two-retry limit and bounded exponential backoff. Permission, schema and other non-transient errors are not retried by the capability.
- `ois/kernel/postgres.py`: `PostgresDurableExecutionStore` stores current checkpoints, immutable checkpoint history, idempotency results and side-effect outbox records. Recovery checks checkpoint hashes.
- `ois/kernel/postgres_stores.py`: PostgreSQL-backed idempotency and append-only evidence adapters. A tenant-isolation migration for these shared tables remains required before multi-tenant production.

These are repository source interfaces, not evidence that an OCIF workflow has been deployed or run against them.

## Required OCIF capability contract

The branch implements `OCIFImportCapability` and `register_ocif_import_capability(...)` for explicit registration of `ocif.import.consume@1.0.0`. The composition root must supply a durable importer and registry. The contract declares:
- a strict input schema for a validated envelope reference or bounded payload;
- least-privilege permission such as `ocif.evidence.import`;
- low risk and no external side effects for local import only;
- explicit timeout and retry limits;
- deterministic idempotency key derived from the OCIF import request identity;
- output schema containing import result, source/capture identity and evidence references.

Do not grant a general-purpose agent direct write access to the OCIF database. The registered capability is the only intended writer. If the operation changes external systems or transfers protected evidence, use a separately reviewed capability with the required approval and access controls.

## Execution sequence

1. A trusted caller supplies tenant identity and a stable invocation ID; an LLM plan cannot set or grant either authority.
2. The OIS registry resolves the exact capability ID and version.
3. Kernel schema validation runs before policy evaluation.
4. Policy checks tenant, permission, risk and approval requirements. A denied decision must not call the OCIF importer.
5. `production/ocif_runtime.py` composes OIS with PostgreSQL checkpoint, evidence and idempotency stores and the real `ocif.PostgresOCIFStore`. Startup initializes durable schemas and requires explicit `ocif.evidence.import` permission. The SQLite consumer remains the local reference implementation. OIS evidence/idempotency tenant isolation remains a release gate.
6. The importer validates the contract and provenance and applies idempotent database writes.
7. OIS records execution, authorization, outcome, failure and recovery evidence. OCIF records its own import/quarantine events. Correlate them by invocation ID, OIS execution ID and evidence IDs.
8. The capability retries only classified transient failures with a hard attempt cap, bounded backoff and the same invocation ID. Do not retry schema incompatibility, permission denial, blocked sources or missing/tampered evidence.
9. After restart, recover from durable checkpoint history, reconcile the import key and verify that a repeated invocation does not create a second observation.

## Required conformance tests

- Missing permission and wrong tenant: denied, no OCIF row written, denial evidence present.
- Valid permission: capability runs, output schema passes, import event and OIS execution evidence correlate.
- Same invocation retried: one observation, stable idempotency result.
- Transient storage failure: retry count stays within configured limit and delay stays within maximum.
- Schema/provenance failure: quarantined/rejected with reason; no success result.
- Process interruption: recover from a valid durable checkpoint; corrupted checkpoints are skipped/rejected and recovery is evidenced.
- Evidence store unavailable: fail closed for operations requiring audit evidence.
- Model-generated plan without trusted authorization: no execution.

## Readiness statement

The branch contains the versioned capability, explicit registration helper, bounded transient retry logic, PostgreSQL composition and a live-PostgreSQL restart/replay conformance test against the real OCIF consumer. Latest USIE CI passes; current OCIF PostgreSQL CI and OIS security/conformance workflows must finish successfully. Multi-tenant rollout remains blocked until PostgreSQL evidence/idempotency tenant isolation is reviewed and verified. Contract `0.1.0` remains a candidate until explicit USIE and OCIF owner approval.
