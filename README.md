# Niceone Obsidian

## OIS — Obsidian Intelligence System

Niceone Obsidian is a governed, stateful, capability-driven AI execution and intelligence platform.

OIS (Obsidian Intelligence System) is the intelligence and execution system underneath the Niceone platform. It is designed to coordinate cognition, planning, capabilities, agents, tools, workflows, knowledge, memory, policy, execution, validation, recovery, measurement, learning, and controlled evolution.

> **Core principle:** governed autonomy — reasoning can propose, but policy, authorization, execution, validation, and evidence determine what may actually happen.

## Operating Doctrine

OIS follows two complementary control loops.

### Engineering lifecycle

```text
STRUCTURE
   ↓
REGISTER
   ↓
CONTRACT
   ↓
AUDIT
   ↓
EVIDENCE
   ↓
KERNEL
   ↓
ACTIVATE
```

### Intelligence lifecycle

```text
THINK
   ↓
VERIFY
   ↓
AUTHORIZE
   ↓
ACT
   ↓
VALIDATE
   ↓
MEASURE
   ↓
LEARN
   ↓
EVOLVE
   ↺
```

## Architecture

The system is organized around:

- OIS Control Plane
- OIS Kernel
- Cognition
- Planning
- Capability Registry
- Agent Registry
- Tool Registry
- Workflow Registry
- Model Gateway
- Knowledge and Memory
- Policy and Governance
- Execution Runtime
- Validation
- Recovery
- Observability
- Measurement
- Learning
- Controlled Evolution

### High-level execution flow

```text
OBJECTIVE
   ↓
COGNITION
   ↓
CONTEXT / KNOWLEDGE
   ↓
PLANNING
   ↓
POLICY / AUTHORIZATION
   ↓
CAPABILITY ROUTING
   ↓
ORCHESTRATION
   ↓
DELEGATION
   ↓
EXECUTION
   ↓
VALIDATION
   ↓
STATE / EVIDENCE
   ↓
MEASUREMENT
   ↓
LEARNING
   ↓
CONTROLLED EVOLUTION
```

## Capability-Driven Execution

Capabilities provide stable interfaces between intent and implementation. Agents and tools act as replaceable execution providers behind governed capability contracts.

```text
OBJECTIVE
   ↓
CAPABILITY CONTRACT
   ↓
CAPABILITY REGISTRY
   ↓
POLICY / AUTHORITY
   ↓
AGENT / TOOL ROUTING
   ↓
EXECUTION
```

A capability should have explicit identity, version, input/output contract, permissions, dependencies, risk, timeout/retry behavior, validation requirements, evidence status, and activation state.

## Execution Safety Boundary

LLM output is treated as a proposal, not infrastructure authority.

```text
LLM
 ↓
STRUCTURED INTENT / PLAN
 ↓
POLICY
 ↓
CAPABILITY AUTHORIZATION
 ↓
EXECUTION KERNEL
 ↓
AGENT / TOOL / SANDBOX
 ↓
OBSERVED RESULT
 ↓
VALIDATION
 ↓
STATE / EVIDENCE
```

No reasoning process grants permission by itself.

## Evidence Discipline

Architecture does not automatically mean implementation.

OIS separates architectural intent from verified operational capability:

```text
UNKNOWN
   ↓
DESIGNED
   ↓
IMPLEMENTED
   ↓
TESTED
   ↓
INTEGRATED
   ↓
DEPLOYED
   ↓
ACTIVATED
   ↓
PRODUCTION VERIFIED
```

A GitHub issue being closed, code existing, or a unit test passing does not by itself establish production readiness. Claims about operational capability must be supported by appropriate implementation, testing, integration, runtime, security, observability, recovery, deployment, and rollback evidence.

## Validation and Recovery

Validation is a first-class part of execution.

```text
INPUT
 ↓
PLAN
 ↓
AUTHORIZATION
 ↓
EXECUTION
 ↓
OUTPUT
 ↓
STATE
 ↓
EVIDENCE
```

Failures use bounded recovery strategies such as:

```text
FAILURE
 ├── RETRY
 ├── FALLBACK
 ├── REPLAN
 ├── ROLLBACK
 └── ESCALATION
```

Recovery must avoid infinite retries, uncontrolled recursion, repeated unsafe actions, hidden failures, and silent state corruption.

## Observability, Measurement, and Learning

Meaningful executions should produce traceable evidence covering execution identity, workflow, capability, agent, tool, model, policy decision, state, validation result, failure/recovery information, latency, cost, outcome, and version.

```text
EXECUTION
   ↓
TELEMETRY
   ↓
MEASUREMENT
   ↓
ATTRIBUTION
   ↓
LEARNING
   ↓
IMPROVEMENT CANDIDATE
```

Learning must preserve evidence, confidence, uncertainty, affected capability/version, and provenance.

## Controlled Evolution

Learning does not directly mutate production.

```text
LEARNING
   ↓
CANDIDATE
   ↓
SIMULATION / REPLAY
   ↓
EVALUATION
   ↓
POLICY CHECK
   ↓
APPROVAL
   ↓
VERSION
   ↓
CANARY
   ↓
MEASUREMENT
   ↓
PROMOTE / ROLLBACK
```

> **Learning proposes. Governance authorizes. Execution activates. Measurement determines whether the change survives.**

Production changes must be versioned, observable, measurable, and reversible.

## Repository and Development Workflow

```text
Architecture
   ↓
Issue
   ↓
Dedicated Branch
   ↓
Implementation
   ↓
Tests
   ↓
Pull Request
   ↓
Review
   ↓
Validation
   ↓
Merge
   ↓
Integration
   ↓
Evidence
   ↓
Activation
```

The repository is the implementation source of truth. GitHub Projects provide the execution and roadmap control layer. Tests, CI, pull requests, runtime evidence, and deployment evidence provide verification signals.

## GitHub Project

The intended project is:

**OIS — Obsidian Intelligence System**

### Workflow

```text
BACKLOG
   ↓
READY
   ↓
IN PROGRESS
   ↓
REVIEW
   ↓
VALIDATION
   ↓
BLOCKED
   ↓
DONE
```

### Evidence status

```text
UNKNOWN
DESIGNED
IMPLEMENTED
TESTED
INTEGRATED
DEPLOYED
ACTIVATED
PRODUCTION VERIFIED
```

### Primary areas

```text
Control Plane
Kernel
Supervisor
Planner
Capabilities
Agents
Tools
Models
Knowledge
Memory
Validation
Recovery
Observability
Security
Deployment
Learning
Evolution
```

The Project is an execution-control layer, not a replacement for implementation evidence.

## Roadmap

The major architectural delivery sequence is:

```text
M1  Kernel Hardening
 ↓
M2  Supervisor Integration
 ↓
M3  Agent & Capability Fabric
 ↓
M4  Tool Registry
 ↓
M5  Model Gateway
 ↓
M6  Durable Runtime
 ↓
M7  Control Plane
 ↓
M8  Knowledge / Semantic World
 ↓
M9  Observability / Security
 ↓
M10 End-to-End Conformance
 ↓
M11 Production Readiness
 ↓
M12 Controlled Evolution
```

The immediate dependency chain is:

```text
Kernel
  ↓
Supervisor
  ↓
Agent Registry
  ↓
Capability Registry
  ↓
Policy
  ↓
Orchestrator
  ↓
Execution
  ↓
Validation
```

## Production Readiness

OIS does not equate documentation, implementation, or passing unit tests with production readiness.

A production capability requires appropriate evidence across:

```text
IMPLEMENTATION
   ↓
TESTING
   ↓
INTEGRATION
   ↓
RUNTIME
   ↓
SECURITY
   ↓
OBSERVABILITY
   ↓
RECOVERY
   ↓
PERFORMANCE
   ↓
DEPLOYMENT
   ↓
ROLLBACK
   ↓
OPERATIONAL VERIFICATION
```

## Governance and Security

OIS follows least-privilege and explicit authorization principles. Governance applies to capabilities, agents, tools, models, workflows, permissions, data access, external side effects, production changes, schema changes, and architecture evolution.

Core invariants include:

1. No unverified action.
2. No unauthorized action.
3. No unvalidated activation.
4. No unmeasured production change.
5. No learning without evidence.
6. No evolution without versioning.
7. No unrestricted infrastructure authority from model output.
8. Consequential actions cross explicit execution boundaries.
9. Production changes have rollback paths.
10. Architectural possibility is never presented as verified implementation.

## Current Status

This is a **development repository**.

The repository contains implemented OIS foundations and ongoing feature work. The complete target architecture is broader than the currently verified implementation.

Current capability status must be determined from repository code, tests, integration evidence, runtime evidence, and deployment evidence rather than architecture documents alone.

## Project Objective

Niceone Obsidian aims to provide a unified platform in which:

```text
Knowledge
+
Cognition
+
Policy
+
Capabilities
+
Agents
+
Tools
+
Models
+
Execution
+
Validation
+
Recovery
+
Observability
+
Measurement
+
Learning
+
Controlled Evolution
```

operate as one coherent, stateful, governable intelligence and execution system.

## Status

**Project:** Niceone Obsidian Intelligence System  
**Repository:** `niceoneobsidian/niceone-obsidian`  
**Default branch:** `main`  
**Architecture:** Capability-driven, stateful, governed AI execution platform  
**Development model:** Evidence-driven, test-gated, versioned, observable, and reversible  
**Production status:** Under controlled implementation and integration
# branch protection test Fri Aug 21 08:46:13 EDT 2026
# branch protection test Fri Aug 21 08:49:12 EDT 2026
# branch protection enforcement test Fri Aug 21 09:01:06 EDT 2026
# branch protection PR test
