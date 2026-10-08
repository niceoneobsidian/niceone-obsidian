# Canonical Architecture Overview

## 1. Purpose

ODI is a governed design-intelligence platform. Its job is to transform design objectives into validated, evidence-backed outputs while preserving provenance, policy boundaries, and reversible evolution.

## 2. Planes

### Control Plane

Owns intent intake, configuration, registries, policy, authorization, lifecycle state, and governance decisions.

### Intelligence Plane

Owns context assembly, knowledge retrieval, reasoning, planning, design-system synthesis, decision formation, and routing.

### Execution Plane

Owns capability invocation, tool execution, agent delegation, workflow execution, media generation, document generation, and production handoff.

### Evaluation Plane

Owns structural validation, semantic evaluation, visual review, accessibility, brand compliance, production preflight, and benchmark execution.

### Evidence Plane

Owns provenance, artifacts, traces, decisions, validation results, and evidence packages.

### Evolution Plane

Owns replay, experiments, candidate improvements, policy review, versioning, canarying, promotion, and rollback.

## 3. Canonical Dependency Direction

```text
interfaces
   ↓
contracts / schemas
   ↓
core domain
   ↓
registries
   ↓
knowledge + context
   ↓
reasoning + planning
   ↓
orchestration
   ↓
capabilities
   ↓
execution adapters
   ↓
validation / evidence
   ↓
observability
   ↓
evaluation / learning
   ↓
evolution
```

Infrastructure adapters must not leak provider-specific assumptions into the domain layer.

## 4. Capability Boundary

A capability is the stable interface between intent and implementation.

```text
Capability
├── identity
├── version
├── input_schema
├── output_schema
├── permissions
├── dependencies
├── risk_class
├── timeout_policy
├── retry_policy
├── validation_requirements
├── evidence_requirements
└── lifecycle_state
```

Agents, tools, models, and external services implement or provide capabilities; they do not redefine the capability contract at runtime.

## 5. Design Intelligence Domains

```text
Design Intelligence
├── brand
├── identity
├── visual-language
├── typography
├── color
├── layout
├── ui-ux
├── illustration
├── image
├── video
├── presentation
├── packaging
├── signage
├── social
├── marketing
├── production
└── accessibility
```

These domains are capability families. The kernel remains domain-neutral.

## 6. Memory Model

ODI separates:

- **Knowledge:** curated, reusable, versioned domain information.
- **Evidence:** source-backed observations and artifacts.
- **Working context:** task-scoped assembled context.
- **Interaction memory:** durable information derived from prior executions.
- **Operational state:** current workflow and execution state.

The same retrieval infrastructure may serve several streams, but their semantics and governance remain distinct.

## 7. Execution Lifecycle

```text
REQUEST
  ↓
INTENT NORMALIZATION
  ↓
CONTEXT ASSEMBLY
  ↓
PLAN
  ↓
POLICY CHECK
  ↓
CAPABILITY ROUTING
  ↓
EXECUTE
  ↓
OBSERVE
  ↓
VALIDATE
  ↓
PACKAGE EVIDENCE
  ↓
MEASURE
  ↓
LEARN / CLOSE
```

Failure paths are bounded:

```text
FAILURE → RETRY → FALLBACK → REPLAN → ROLLBACK → ESCALATE
```

Not every failure uses every step.
