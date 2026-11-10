# ADR: OIS / OSIS Social-Domain Ownership Boundary

**Status:** Proposed for owner ratification  
**Decision scope:** Domain ownership and integration boundaries only. No code movement, record migration or connector change is authorized by this ADR.

## Context

OIS is the governed intelligence and execution foundation: identity/tenant context, policy and risk evaluation, capability registration, authorization, approvals, execution lifecycle, durable state, idempotency, evidence and controlled side effects.

OSIS is the standalone social-intelligence system in the marketing workspace. It owns social audience research, competitor intelligence, social signals, content engineering, distribution operations, channel workflows, performance analytics and growth learning.

The OIS repository currently contains `ois/domains/social_intelligence`, including:
- TikTok profile/search acquisition through SociaVault;
- analytics and post creation through bundle.social;
- social capability contracts, platform-specific schemas and provider adapters;
- social-domain permissions and domain labels.

The structural-fabrics architecture also lists Social Intelligence as an OIS fabric. These are domain-specific capabilities, not merely generic transport primitives. Their current placement creates overlapping ownership with OSIS.

## Proposed decision

1. **OSIS owns the social domain.** Canonical social schemas, platform/account models, audience and competitor intelligence, research ingestion, content ideation/engineering, publishing workflows, analytics, attribution and growth-learning logic belong to OSIS.
2. **OIS owns generic governance and execution primitives.** OIS may provide generic capability registration/execution, authorization, policy/risk evaluation, approval, tenant context, credential isolation, source transport, durable state, idempotency, audit evidence and controlled side-effect execution.
3. **OIS does not own social strategy or social-domain semantics.** It must not become the canonical home for platform-specific social profiles, post models, audience intelligence, editorial calendars, channel analytics or growth metrics.
4. **OSIS may call OIS through a versioned capability contract.** OSIS remains the system of record for social workflows and data. OIS acts only as a governed execution provider where explicitly integrated and approved.
5. **No implicit dependency exists.** OSIS remains independently operable. No OIS integration is assumed until both systems' owners approve an interface, threat model, data contract and operational responsibilities.
6. **Existing OIS social code remains untouched pending a migration decision.** Do not delete, move, rename or silently reclassify its modules or records in this documentation-only phase.

## Responsibility matrix

| Concern | OIS | OSIS |
|---|---|---|
| Tenant identity, authorization and policy | Accountable | Consumes explicit interface if integrated |
| Credential vault boundary and source transport | Accountable for generic primitives | Owns provider selection/configuration intent; secrets remain outside OSIS knowledge pages |
| Capability execution, approvals and audit evidence | Accountable | Requests approved operations through contract |
| Social account/platform domain model | Generic identity hooks only | Accountable |
| Audience, competitor and trend intelligence | No domain ownership | Accountable |
| Content strategy, ideation and content engineering | No domain ownership | Accountable |
| Scheduling, publishing workflow and channel operations | Generic governed side-effect primitive only | Accountable |
| Social analytics, attribution and growth learning | No domain ownership | Accountable |
| Engineering lifecycle and release gates | Accountable for OIS | Accountable for OSIS product release within its own governance |

## Migration and compatibility principles

Any future extraction of `ois/domains/social_intelligence` must:
- inventory imports, public APIs, schemas, tests, environment variables, provider credentials and persisted records;
- define a versioned OSIS-owned domain contract and compatibility adapters;
- preserve evidence provenance and historical identifiers;
- migrate records with verified ownership and idempotent replay;
- retain OIS policy enforcement for consequential operations only through an explicit, reviewed interface;
- include contract, integration, security, rollback and data-reconciliation tests;
- be executed in a reviewed PR with an owner, migration window and rollback criteria.

## Consequences

- OIS remains a reusable governed execution foundation rather than a second social-management product.
- OSIS becomes the single canonical owner of social-domain intelligence and workflows.
- Generic source/credential/policy/execution infrastructure can be reused without duplicating domain ownership.
- Existing OIS social modules are classified as legacy/candidate implementation pending explicit disposition; this ADR does not claim they have been extracted or disabled.

## Ratification required

This ADR is **proposed**, not an adopted owner decision. The system owner must explicitly approve the responsibility matrix and migration direction before any code or data is moved. Until then, preserve current source and records and do not introduce new social-domain scope into OIS.
