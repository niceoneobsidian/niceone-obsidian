# OIS prioritized hardening and intelligence delivery

This plan is the implementation order for strengthening OIS using existing boundaries.
It intentionally does not introduce a second execution engine, source gateway, or model registry.

## Stage 1 — Execution safety and evidence provenance

### Implemented in this change set
- Governance authorization denies non-canonical input payloads and records a deterministic denial digest, decision provenance, and audit event instead of allowing serialization errors to escape the control boundary.
- Source provenance recursively redacts credential-like metadata keys before serialization.
- Model requests reject invalid token limits and non-finite/negative budgets; model specs reject invalid cost and token-capacity settings.
- A preferred model is ranked ahead of ordinary priority, while unhealthy or over-budget preferred models may fall back deterministically.
- Knowledge facts require non-empty subject, predicate, and source values, and confidence is finite and bounded.
- Regression tests cover each behavior.

### Required before production activation
- Confirm repository secret scanning, push protection, branch protection, and required checks in live GitHub settings.
- Test PostgreSQL tenant row-level security and authorization with cross-tenant integration cases.
- Verify production evidence and governance audit writes are durable under transaction failure and worker restart.
- Run staging fault injection for approval, budget, stale lease/epoch, side-effect replay, and rollback.
- Keep secrets out of prompts, evidence payloads, provenance metadata, and logs; redaction is defense in depth, not permission to pass secrets into metadata.

## Stage 2 — Knowledge ingestion and retrieval

### Implemented in this change set
- Added SQLite indexes for exact predicate/object fact lookups and subject/version history.
- Exact fact retrieval now uses indexed SQL equality instead of loading every fact for a predicate and filtering in Python.
- Canonical JSON serialization is shared between fact writes and exact retrieval so nested objects and non-ASCII text remain deterministic.

### Next integration increments
1. Add an ingestion adapter contract for files and URLs that preserves source URI, media type, retrieval timestamp, parser/version, source hash, extraction status, and page/section offsets.
2. Add a parser adapter (evaluate Marker against representative PDFs and office documents) without making it a mandatory runtime dependency until measured.
3. Store immutable raw artifacts separately from extracted/chunked text; derived chunks must point to source evidence and carry extraction/model versions.
4. Add tenant-scoped lexical retrieval first; benchmark Typesense against existing retrieval before choosing a new search dependency.
5. Add retrieval evaluation fixtures for exact IDs, fuzzy terms, source citation correctness, stale content, duplicate ingestion, and tenant isolation.

### Acceptance gates
- Every returned passage identifies its source evidence and extraction version.
- Re-ingesting identical bytes is idempotent.
- Updated content creates a new version rather than silently overwriting historical evidence.
- Cross-tenant retrieval returns no results.
- Search quality and latency are measured against a committed fixture set before adding a search service.

## Stage 3 — Model and agent optimization

### Implemented in this change set
- Model preference is honored before priority; deterministic fallback remains available when the preferred candidate is unhealthy, incompatible, or over budget.
- Invalid budget and model-capacity configuration is rejected at contract construction.

### Next integration increments
1. Add a task-class routing policy with explicit quality, latency, privacy, and cost constraints.
2. Record selected model/provider/version, routing reason, estimated and actual usage where available, latency, fallback cause, and validation outcome.
3. Evaluate routing on a fixed task set; compare quality and cost with the current default before enabling automatic routing.
4. Keep agent tools capability-scoped, bounded by deadlines and budgets, and unable to bypass the Control Plane or Kernel.
5. Defer fine-tuning, new agent frameworks, and distributed orchestration until an evaluation shows a measurable gap.

## Verification protocol

Run the repository's canonical checks from an activated project virtual environment:

```bash
ruff check .
ruff format --check .
python -m mypy ois production
pytest -q
```

Also run the PostgreSQL integration suite and production-readiness workflow as applicable. Do not claim staging, deployment, live credential rotation, or production verification from unit tests alone.
