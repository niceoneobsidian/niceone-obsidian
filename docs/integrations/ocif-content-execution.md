# OCIF content execution authorization boundary

**Status:** Candidate; sandbox/no-op only.

OCIF owns the research brief, draft content, score formula/version, reviewer decision, content digest, and outcome metrics. OIS owns permission evaluation and the governed execution invocation. The OIS capability introduced on this branch is:

- Capability: ocif.content.execute
- Version: 1.0.0
- Permission: ocif.content.execute
- Domain: content_workflow
- Accepted mode: sandbox_noop
- External side effects: none

## Required execution context

OCIF must present the approval ID, draft ID, SHA-256 content digest, draft version, reviewer ID, and idempotency key. OIS evaluates the capability permission before invoking the capability. The capability rejects any mode other than sandbox_noop and returns a policy-governed invocation ID. OCIF must persist the authorization response and execution receipt with the same digest and idempotency key.

The OCIF workflow releases its row-lock transaction before calling OIS so the independent OIS verifier can read the committed approval. It re-locks and rechecks the approval after authorization and before receipt persistence, closing the edit-between-checks race. The executor is not called when OIS denies the request. A repeated idempotency key may replay only the same receipt for the same approval, draft, and digest.

## Current limitation

This capability proves a governed no-op boundary. It is not a live publishing capability and does not prove platform API behavior, token safety, scheduling, rollback, or outcome attribution. Do not add network publishing adapters to this capability. A live publishing feature needs a separate capability, explicit permission per platform, reviewed consent scopes, bounded retries, duplicate-post protection, audit receipts, and a dedicated end-to-end test.

## Required evidence before release

1. OIS permission-denial test proves the capability does not run.
2. OIS allowed test proves only sandbox_noop is accepted.
3. OCIF PostgreSQL tests prove approval invalidation, denial-before-executor, idempotent replay, and append-only outcomes.
4. The cross-repository vertical slice consumes a real USIE export with artifact hashes verified, imports it into PostgreSQL, restarts the consumer, and verifies duplicate replay and conflicting-payload quarantine.
5. All checks pass on the exact PR head commits. Tenant isolation and security review remain separate production gates.
