# Repository Structural Boundaries

## Canonical Runtime Architecture

```text
Core Contracts
      ↓
Capability Registry
      ↓
Agent Registry
      ↓
Model Registry / Gateway
      ↓
Knowledge + Evidence Fabric
      ↓
Context Engine
      ↓
Planner / Supervisor
      ↓
Orchestrator
      ↓
Execution Runtime
      ↓
Validation Engine
      ↓
Evidence / Observability
      ↓
Design Capability Fabric
```

This is the canonical dependency direction. Domain capabilities consume the platform substrate; provider implementations do not define the platform contract.

## Runtime Mapping

```text
src/odi/
  core/             stable contracts, domain types, lifecycle primitives
  registry/         capability, agent, model registries
  model_gateway/    provider-neutral model routing boundary
  knowledge/        knowledge and evidence retrieval/storage boundary
  context/          context assembly
  planning/         planning contracts and planners
  supervision/      policy checkpoints and recovery decisions
  orchestration/    plan execution coordination
  execution/        side-effect and capability execution runtime
  validation/       quality gates and validation checks
  evidence/         provenance and evidence ledger
  observability/    telemetry and event emission
  design/           design-domain capability fabric
  memory/           persistent/session memory boundary
  evaluation/       benchmark and evaluator boundary
  evolution/        controlled improvement and promotion boundary
  interfaces/       API/CLI/application boundaries
```

## Structural Principles

1. **Contracts before implementations.** Every major runtime boundary has an explicit interface or stable data contract.
2. **Registries before routing.** Capabilities, agents, and models are discoverable through authoritative registries.
3. **Gateway before providers.** Model vendors and execution providers remain replaceable behind adapters.
4. **Evidence is first-class.** Evidence and provenance travel with decisions and executions rather than being reconstructed afterward.
5. **Context precedes planning.** Planning operates on assembled intent, knowledge, and evidence.
6. **Supervision precedes side effects.** Plans pass a policy checkpoint before execution.
7. **Validation follows execution.** Outputs are not considered complete merely because a provider returned successfully.
8. **Observability is part of execution.** Telemetry is emitted as the runtime operates.
9. **Design capabilities remain pluggable.** Brand, identity, typography, UI/UX, image, video, packaging, presentation, and production capabilities plug into the fabric without changing the kernel.
10. **Evolution is governed.** Experiments and self-improvement require evaluation, evidence, promotion rules, and rollback boundaries.

## What Does Not Belong in the Kernel

- Provider-specific image-generation code
- Prompt collections
- UI component implementations
- Raw datasets
- Model weights
- Vendor credentials
- One-off workflow scripts
- Experimental algorithms without contracts
- Unvalidated self-modifying behavior

## What Belongs in the Kernel

Only stable domain contracts and lifecycle primitives required to govern execution belong in `src/odi/core`.

## Knowledge Boundary

`knowledge/` is source-controlled, curated design intelligence. It is not a dump of scraped content. Reusable rules should carry provenance, confidence, scope, and lifecycle metadata.

## Skill Boundary

A skill is an operationally discoverable capability description. A skill may reference capabilities and tools, but its instructions do not bypass policy or execution contracts.

## Workflow Boundary

Workflows compose capabilities. They should be declarative wherever practical and remain inspectable, versioned, testable, and replayable.
