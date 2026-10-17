# OIS Runtime Hardening Rollout

Status: implementation scaffold added; live integration gates remain unverified.

This rollout follows the required order. Do not add orchestration, telemetry, evaluation,
or agent-provider dependencies merely to complete a checklist. OIS remains the authority
for policy, capability resolution, credentials, validation, recovery, and evidence.

## 1. LangGraph recovery verification

### Covered in this change
- The LangGraph adapter now forwards an optional `invocation_id` from graph state to
  `OISSpine.submit`, preserving the caller's idempotency/correlation key at the governed
  execution boundary.
- Unit coverage checks invocation propagation, missing-request rejection, and checkpoint
  state retrieval after rebuilding the graph around the same in-memory checkpointer.

### Required live gate
The in-memory checkpointer test is not evidence of PostgreSQL durability. With a disposable
PostgreSQL test database, add/run integration coverage for:
- checkpoint write/read across a real process restart;
- human-approval interrupt and resume after restart;
- checkpoint corruption and explicit escalation/recovery;
- duplicate delivery and side-effect idempotency;
- lease expiry, stale-worker fencing, and split-brain prevention.

Keep these tests opt-in and marked `integration`/ `recovery`; never silently fall back from a
requested durable checkpointer to in-memory state.

## 2. OpenTelemetry verification

### Covered in this change
- Thread identifiers are fingerprinted before being attached to execution spans, matching the
  existing tenant-fingerprinting approach.
- Unit tests verify stable fingerprints and ensure the raw identifiers are not returned.

### Required live gate
Run against the deployment's actual OTLP collector/exporter configuration. Verify traces and
metrics arrive, graceful shutdown flushes, exporter failures are visible, and sensitive request
content/credentials never appear in telemetry. Correlate spans with execution/invocation IDs,
policy decisions, provider attempts, validation, recovery, and evidence without adding
unbounded identifiers to metric labels. Langfuse remains a decision, not a prerequisite.

## 3. Behavioral evaluation

Build and version a deterministic corpus before selecting another agent framework or provider.
At minimum include:
- successful and denied capability requests;
- malformed model output and command-shaped payloads;
- prompt-injection attempts in user and retrieved content;
- primary-provider failure and policy-permitted fallback;
- timeout, rate limit, duplicate delivery, checkpoint failure, and unknown faults;
- retrieval correctness and provenance when retrieval is exercised;
- task success, independent validation, latency/cost, and evidence completeness.

Record expected outcome, model/provider, prompt/schema version, OIS revision, and evidence
references. Treat provider-generated assertions as untrusted: tests and validators, not the
agent, decide whether work passed.

## 4. Structured-output audit

### Covered in this change
- Adds negative cases for empty, whitespace-only, non-string, list, and command-shaped
  content at the `ModelOutput` boundary.
- Existing agent/gateway tests already cover rejection of command-shaped provider output and
  avoiding memory writes for malformed agent responses.

### Required gate
Trace every model boundary to the schema validator and the OIS authorization/execution boundary.
A structured response is still untrusted data; it is not an authorization token or executable
instruction. Verify schema failures cannot bypass policy, invoke tools, or persist an accepted
assistant response.

Pydantic AI should only be considered if this audit identifies a concrete missing contract that
cannot be addressed by the existing Pydantic-based schemas and validators.

## 5. One controlled provider pilot

Do not start the external provider pilot until gates 1–4 have evidence. Prefer one bounded,
read-only or isolated workflow with:
1. explicit objective and capability contract;
2. policy authorization before side effects;
3. bounded timeout/retry and idempotency;
4. isolated execution and restricted network/credentials;
5. independent OIS validation;
6. evidence/provenance capture;
7. human approval for consequential changes;
8. tested rollback and provider disablement.

Use the existing model gateway and integration/credential boundaries. Do not introduce a second
gateway, policy engine, credential store, provider registry, or orchestration authority. Select
OpenHands, browser-use, Composio, E2B, or another adapter only after the use case and acceptance
criteria are specified; this change intentionally adds no provider dependency.

## Local verification commands

Run from the canonical checkout only after its state has been reconciled with the older checkout.
This change was authored against the GitHub branch; it does not authorize overwriting or merging
either local checkout.

```sh
pytest -q tests/integration/test_langgraph_runtime.py tests/test_observability_telemetry.py tests/evaluation/test_structured_output_contract.py
ruff check ois/integration/langgraph_runtime.py ois/observability_telemetry.py tests/integration/test_langgraph_runtime.py tests/test_observability_telemetry.py tests/evaluation/test_structured_output_contract.py
ruff format --check ois/integration/langgraph_runtime.py ois/observability_telemetry.py tests/integration/test_langgraph_runtime.py tests/test_observability_telemetry.py tests/evaluation/test_structured_output_contract.py
python -m mypy ois
pytest -q
```

These commands are a verification plan, not a claim that they have run. Live PostgreSQL,
Redis, and OTLP collector evidence must be reported separately from unit-test results.
