# Phase C — Autonomous Operations

Phase C turns governed source events into bounded autonomous operations. The
design keeps the Kernel authoritative: source events trigger workflows, policy
decides whether automation may proceed, human approval can pause high-impact
work, and recovery remains bounded and observable.

## Builds 15–20

| Build | Capability | Boundary |
|---|---|---|
| 15 | Source-triggered workflows | Source events select tenant-scoped workflow definitions |
| 16 | Event routing | Typed event envelopes fan out to matching workflow routes |
| 17 | Policy-aware automation | Explicit allow/deny/approval policy before execution |
| 18 | Failure recovery | Bounded retry, replan, pause, escalation, and stop decisions |
| 19 | Human approval gates | Expiring, tenant-scoped approval requests for gated actions |
| 20 | Autonomous operating loops | Event → policy → approval → execution → recovery loop |

## Runtime path

```text
Source Fabric / Outbox
        |
        v
   Event Envelope
        |
        v
    Event Router
        |
        v
Source Workflow
        |
        v
 Automation Policy
   /       |       \\
deny    approve    allow
 |         |         |
stop   Human Gate    |
           |         |
       approve ------+
             |
             v
         Workflow
         Execution
             |
        +----+----+
        |         |
     success    failure
        |         |
       done    Recovery
                  |
       +----------+----------+
       |          |          |
      retry     replan    escalate/stop
       |
       +-----> bounded loop
```

## Safety invariants

1. Workflow matching is tenant/workspace scoped.
2. Disabled workflows never execute.
3. Event routing does not bypass the workflow policy gate.
4. No matching policy rule means **deny**.
5. Approval requests expire and are single-decision.
6. Approval resumes preserve the original event payload and source identity.
7. Retry attempts are bounded.
8. Safety and permission failures never become uncontrolled autonomous retries.
9. Workflow/event execution is idempotent by `(tenant, workspace, workflow, version, event)`.
10. Durable source events remain behind the existing transactional outbox boundary.
11. Autonomous operations do not store OAuth client secrets or access tokens.
12. Kernel execution remains the authoritative capability execution boundary.

## Build 15 — Source-triggered workflows

`SourceWorkflow` defines a versioned tenant/workspace-scoped workflow and a
`WorkflowTrigger`. Triggers can match event type, source, and exact payload
conditions.

The Phase C application boundary registers workflows against the event router
and rejects duplicate workflow IDs.

## Build 16 — Event routing

`EventEnvelope` normalizes source/outbox events into one routing contract.
`InMemoryEventRouter` provides deterministic fan-out for the reference layer;
the PostgreSQL workflow/run schema provides the durable production boundary.

Outbox events can be drained into autonomous operations. A successfully
completed workflow run can then acknowledge the source event.

## Build 17 — Policy-aware automation

`AutomationPolicy` uses explicit ordered rules. Each rule can constrain:

- event type,
- maximum risk,
- whether side effects are allowed,
- required policy tags.

There are only three outcomes: `ALLOW`, `DENY`, or `APPROVAL_REQUIRED`.

## Build 18 — Failure recovery

`FailureRecovery` provides bounded decisions:

- transient/timeout → retry while the limit remains,
- plan → replan,
- state → pause,
- permission/approval → escalate,
- safety → stop,
- unknown → escalate.

This is deliberately separate from the Kernel's existing `RecoveryPolicy`; the
Phase C layer decides workflow-level recovery while the Kernel continues to
control capability-level execution recovery.

## Build 19 — Human approval gates

High-impact workflows can return `WAITING_APPROVAL`. Approval requests are:

- tenant/workspace scoped,
- linked to workflow and event,
- expiring,
- single-decision,
- actor-attributed.

Approval resumes the exact source event context rather than reconstructing a
different event.

## Build 20 — Autonomous operating loops

`AutonomousLoop` implements a bounded control loop:

```text
observe → match → authorize → approve → execute → observe → recover → repeat
```

The loop never retries indefinitely. Every terminal or waiting state is
explicit and inspectable.

## Production boundary

The reference implementation uses in-memory routing and approval stores for
deterministic tests. Production adapters should bind the same contracts to
PostgreSQL and use the existing durable execution/idempotency/fencing
boundaries. The autonomous layer should call `IntegratedExecution` or another
Kernel-owned executor for real capability execution; it must not invoke
provider APIs directly.