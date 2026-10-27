# OCIF Document Processing — OIS Boundary

**Status:** Proposed capability implementation on this branch; not merged or production-verified.

## Authority split

- USIE owns authorized source acquisition, append-only capture history, original artifact records, hashes and capture outcomes.
- OCIF owns document-processing records, derived output references, knowledge records and retrieval.
- OIS owns policy authorization, capability invocation, durable execution state, evidence, recovery and audit.
- Docling is an optional parser provider behind OCIF's adapter boundary. It is not a mandatory OIS dependency or a separate service.

## Capability

- ID: `ocif.document.process`
- Version: `1.0.0`
- Permission: `ocif.document.process`
- Domain: `knowledge_ingestion`
- Input: source/capture/artifact identities, SHA-256, size, media type, options digest, idempotency key.
- Output: extraction status, input lineage, processor/version, output references and warnings.
- Scope: PDF only in this initial capability.
- Retry: at most two retries for explicit transient timeout/connection errors. Parser, schema, hash and media failures do not retry automatically.

The capability accepts artifact references and metadata, not arbitrary file paths or document bytes from model output. The injected processor must resolve the artifact through a trusted OCIF/USIE integration, verify the bytes against the supplied hash, enforce size/time/resource limits, and store outputs under an approved evidence policy. This branch does not invent a USIE export API.

## Evidence and recovery

OISSpine/Kernel records the governed invocation and evidence events. The output carries capture/artifact IDs, input hash, options digest, processor identity/version, idempotency key, status, warnings and output references. The consumer must persist its own extraction record in OCIF and make the write idempotent. A retry must reuse the same idempotency key and may not overwrite a conflicting result.

Do not treat an OIS invocation receipt as proof that PDF extraction was correct. Quality requires OCIF benchmark evidence, provenance validation and integration tests. Failed/quarantined/unsupported parser outcomes are surfaced as failed capability invocations; partial extraction is an explicit successful invocation with a partial extraction status.

## Required gates before activation

- [ ] OCIF benchmark corpus and baseline run are recorded.
- [ ] USIE producer interface/export is explicitly selected and tested; no guessed filesystem contract.
- [ ] Artifact hash is rechecked at the trusted processor boundary.
- [ ] Permission-denial test proves the processor is never called.
- [ ] Transient retry is bounded; non-transient failures are not retried.
- [ ] Repeated invocation and process restart preserve one extraction record per idempotency key.
- [ ] PostgreSQL-backed OIS execution/evidence is used in production composition, not only in-memory spine tests.
- [ ] Evidence retention/access checks, security review, and exact-head CI pass.
- [ ] No publishing side effect is enabled.
- [ ] Owner review approves capability contract and permission naming.

## Separate service decision

Do not deploy Docling as a separate service at this stage. Reconsider only after measurements show sustained concurrency, memory isolation, worker scaling, or independent deployment/recovery requirements that outweigh the added API, queue, observability and operations burden.
