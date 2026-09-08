# OIS Sovereign Control Architecture

## Authority model

OIS is the sovereign architecture and system of control. External projects are providers, infrastructure, or references; none becomes the OIS authority.

```text
Human / API
    |
    v
Intent Intake -> Typed OIS Request
    |
    v
+---------------- OIS CONTROL PLANE ----------------+
| Policy / Auth | Registries | Approval | Evidence  |
+------------------------+---------------------------+
                         |
                         v
                 Supervisor / Planner
                         |
                         v
                 +-------+-------+
                 |   OIS KERNEL |
                 +-------+-------+
                         |
              +----------+----------+
              |                     |
              v                     v
      LangGraph Runtime      Temporal Candidate
      agent orchestration    durable workflow layer
              |                     |
              +----------+----------+
                         v
                 Execution Runtime
                         |
                         v
                PostgreSQL Canonical State
                         |
                         v
                Validation / Recovery
                         |
                         v
                    Evidence / OTel

Tool Fabric:
  OIS Tool Registry -> Policy -> MCP / n8n -> observed result

Reference systems:
  Dify / Flowise -> UX, workflow, RAG, model/tool-management patterns only

Security baseline:
  PostgreSQL roles + RLS + least privilege + explicit tenant context

## Provider ownership

| System | OIS role | OIS remains authoritative for |
|---|---|---|
| LangGraph | Agent/workflow orchestration provider | policy, contracts, registry, execution authority, evidence |
| PostgreSQL | Canonical durable state | schema governance, tenancy, integrity, lifecycle |
| Supabase-derived patterns | Security reference | OIS roles, RLS, auth boundaries, security tests |
| Temporal | Durability candidate | adoption gate, workflow contract, evidence, policy |
| n8n | Integration provider | tool registration, authorization, side-effect governance |
| MCP | Tool protocol | tool identity, authorization, allowlist, evidence |
| Dify | Reference system | none; patterns are selectively reimplemented |
| Flowise | Reference/prototyping system | none; visual workflow ideas only |

## Non-negotiable boundaries

1. Model output is never infrastructure authority.
2. Natural language compiles into typed OIS requests.
3. Every external tool is registered before invocation.
4. Policy and authorization execute before side effects.
5. PostgreSQL is the canonical state store; local SQLite is not the production system of record.
6. Temporal remains disabled as a hard dependency until Recovery Conformance proves the required durability semantics.
7. LangGraph can orchestrate agents but cannot bypass OIS governance.
8. Dify/Flowise patterns cannot silently become architectural dependencies.
9. Evidence is emitted for authorization, execution, validation, recovery and outcome.
10. Production evolution is versioned, measurable and reversible.

## Implementation status

Implemented in this change:

- `ois/sovereign/contracts.py` — provider-neutral request/result/runtime contracts.
- `ois/sovereign/control_plane.py` — policy-before-runtime execution facade.
- `ois/sovereign/adapters/langgraph.py` — LangGraph orchestration adapter.
- `ois/sovereign/adapters/temporal.py` — Temporal durability candidate seam.
- `ois/sovereign/tool_fabric.py` — registry-first n8n/MCP routing boundary.
- `migrations/20260908_ois_sovereign_security.sql` — PostgreSQL tenant-isolation/RLS baseline.

The existing `PostgresDurableExecutionStore` remains the canonical OIS persistence implementation and is intentionally not duplicated. The new layer composes around it.

## Activation gates

A provider becomes production-active only after:

```text
CONTRACT
  -> UNIT TEST
  -> INTEGRATION TEST
  -> RECOVERY CONFORMANCE
  -> SECURITY TEST
  -> OBSERVABILITY TEST
  -> RUNTIME EVIDENCE
  -> APPROVAL
  -> ACTIVATION
```

This architecture therefore avoids a super-fork: OIS owns the control plane, while external systems remain replaceable implementation providers.
