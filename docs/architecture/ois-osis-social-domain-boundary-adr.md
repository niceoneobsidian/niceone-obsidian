# ADR: OIS / OSIS Social-Domain Ownership Boundary

**Status:** Accepted — ownership boundary  
**Decision basis:** Explicit direction to resolve system ownership before further record reorganization, consistent with the established standalone OSIS scope.  
**Decision scope:** Domain ownership and integration boundaries only. No code movement, record migration or runtime integration is authorized by this ADR.

## Context

OIS is the governed intelligence and execution foundation: identity/tenant context, policy and risk evaluation, capability registration, authorization, approvals, execution lifecycle, durable state, idempotency, evidence and controlled side effects.

OSIS is the standalone social-intelligence system in the marketing workspace. It owns social audience research, competitor intelligence, social signals, content engineering, distribution operations, channel workflows, performance analytics and growth learning.

The OIS repository currently contains `ois/domains/social_intelligence`, including:
- TikTok profile/search acquisition through SociaVault;
- analytics and post creation through bundle.social;
- social capability contracts, platform-specific schemas and provider adapters;
- social-domain permissions and domain labels.

The structural-fabrics architecture also lists Social Intelligence as an OIS fabric. These are domain-specific capabilities, not merely generic transport primitives. Their current placement creates overlapping ownership with OSIS.

## Accepted decision

1. **OSIS owns the social domain.** Canonical social schemas, platform/account models, audience and competitor intelligence, research ingestion, content ideation/engineering, publishing workflows, analytics, attribution and growth-learning logic belong to OSIS.
2. **OIS owns generic governance and execution primitives.** OIS provides generic capability registration/execution, authorization, policy/risk evaluation, approval, tenant context, credential isolation, source transport, durable state, idempotency, audit evidence and controlled side-effect execution.
3. **OIS does not own social strategy or social-domain semantics.** It is not the canonical home for platform-specific social profiles, post models, audience intelligence, editorial calendars, channel analytics or growth metrics.
4. **No OIS dependency is imposed on OSIS.** OSIS remains independently operable. Any future OSIS call to OIS must be an explicit, versioned, separately approved integration; no integration is assumed by this decision.
5. **Existing OIS social code is legacy/candidate scope pending disposition.** Its current presence in the OIS repository does not confer domain ownership. Do not add new social-domain features there.
6. **No automatic extraction or migration is authorized.** Existing OIS social modules, configuration, provider credentials and records remain untouched until a separate implementation/migration proposal is reviewed and approved.

## Responsibility matrix

| Concern | OIS | OSIS |
|---|---|---|
| Tenant identity, authorization and policy | Accountable | Consumes explicit interface only if later integrated |
| Credential vault boundary and source transport | Accountable for generic primitives | Owns provider selection/configuration intent; secrets remain outside OSIS knowledge pages |
| Capability execution, approvals and audit evidence | Accountable | Requests approved operations only through an explicitly approved contract |
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
- retain OIS policy enforcement for consequential operations only through an explicit, separately approved interface;
- include contract, integration, security, rollback and data-reconciliation tests;
- be executed in a reviewed PR with an owner, migration window and rollback criteria.

## Consequences

- OIS remains a reusable governed execution foundation rather than a second social-management product.
- OSIS is the single canonical owner of social-domain intelligence and workflows.
- Generic source/credential/policy/execution infrastructure can be reused without duplicating domain ownership.
- The existing OIS social modules are not canonical and should receive no new domain features; they remain in place until an independently approved extraction plan exists.
- The decision does not create a dependency between the two systems.

## Change control

This ADR resolves ownership. It does not authorize code extraction, data movement, connector shutdown, credential changes or runtime integration. Those actions require a separate implementation proposal and approval.
