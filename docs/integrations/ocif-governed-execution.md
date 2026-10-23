# OCIF Governed Execution Boundary

**Status:** Candidate integration implementation and acceptance plan. A versioned capability and explicit registry helper exist; production composition and deployment are not yet verified.

## Existing OIS control surfaces verified in source

- `ois/integration/spine.py`: `OISSpine.submit()` creates execution identity, checkpoints the request, calls the Kernel and returns execution status plus evidence events.
- `ois/kernel/runtime.py`: validates capability input, invokes the policy engine before execution, emits authorization evidence, checkpoints execution, supports idempotency and records recovery decisions.
- `ois/kernel/policy.py`: `DefaultPolicyEngine` evaluates tenant identity, required permissions, risk and irreversible side effects; denied authorization raises `AuthorizationDenied`.
- `ois/kernel/recovery.py`: `RecoveryPolicy` classifies failures and caps retry/recovery decisions. The `ocif.import.consume` capability retries only known transient timeout/connection/SQLite-lock errors, with a hard two-retry limit and bounded exponential backoff. Permission, schema and other non-transient errors are not retried by the capability.
- `ois/kernel/postgres.py`: `PostgresDurableExecutionStore` stores current checkpoints, immutable checkpoint history, idempotency results and side-effect outbox records. Recovery checks checkpoint hashes.
- `ois/kernel/evidence.py`: evidence ledger interfaces and SQLite durable evidence implementation.

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
5. Execution is persisted through the configured checkpoint, evidence and idempotency stores; use PostgreSQL-backed stores for a shared production runtime. The branch exposes `idempotency` and `recovery` injection on `OISSpine`. Tests cover denied-before-invoke behavior, SQLite-backed replay across store instances, stable invocation IDs, a hard retry cap and bounded backoff. Latest CI for this expanded test set is pending.
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

The branch now contains the versioned capability, explicit registration helper, bounded transient retry logic and tests. The cross-repository USIE export → OCIF import test passes in OCIF CI. Full latest USIE CI and OIS CI must pass, and production wiring must select durable PostgreSQL stores and provide a reviewed importer adapter before deployment. Contract `0.1.0` remains a candidate until explicit USIE and OCIF owner approval.
