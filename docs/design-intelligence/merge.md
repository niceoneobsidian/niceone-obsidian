# ODI → OIS Consolidation

## Decision

Obsidian Design Intelligence (ODI) is consolidated into the Niceone Obsidian (OIS) repository as a domain layer. OIS remains the single execution and governance authority.

## Source

- Repository: `niceoneobsidian/obsidian-design-intelligence`
- Source commit: `ccaeb874384fb2c9f8eb69887180ca0d87ef0364`

## Migrated

- `src/odi/design/*` → `ois/design_intelligence/*`
- Design capability documentation → `docs/design-intelligence/`
- Design knowledge entry → `knowledge/design-intelligence/`
- Design skill → `skills/design/`
- Design workflow documentation → `workflows/design-intelligence/`
- Design schemas → `schemas/design-intelligence/`
- Design capability tests → `tests/design_intelligence/`

## Intentionally not migrated as duplicate infrastructure

The following ODI structures are superseded by existing OIS authorities and therefore are not copied as second implementations:

- ODI core contracts/types
- ODI capability/agent/model registries
- ODI model gateway
- ODI context/planning/supervision/orchestration runtimes
- ODI execution runtime
- ODI validation engine
- ODI evidence ledger
- ODI observability/telemetry
- ODI memory store
- ODI evolution runtime
- ODI bootstrap/interface scaffolding
- ODI packaging metadata (`pyproject.toml`)

## Architectural rule

```text
Design intelligence proposes
        ↓
OIS policy authorizes
        ↓
OIS execution produces
        ↓
OIS validation verifies
        ↓
OIS evidence records
        ↓
OIS measurement / learning governs evolution
```

No new design provider should introduce its own execution kernel. Providers belong behind the OIS capability, policy, registry, execution, and evidence boundaries.

## Follow-up

1. Wire design capability definitions into the canonical OIS capability registry.
2. Replace any remaining design-domain local contracts with OIS kernel contracts.
3. Add an end-to-end design vertical-slice conformance test.
4. Reconcile design schemas with OIS canonical task/evidence/validation schemas where overlap exists.
5. Only after CI and integration evidence pass should the legacy ODI repository be treated as removable.