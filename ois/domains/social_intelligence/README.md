# OIS Social Intelligence Fabric

This domain package maps the 394 recommended Social Intelligence structures into the existing OIS Kernel contracts and registries.

## Existing OIS anchors

- `ois/kernel/contracts.py` — `CapabilityContract`, `AgentContract`, `ToolContract`, `PolicyEngine`, `Validator`.
- `ois/kernel/state.py` — `ExecutionIdentity` and `ExecutionContext`.
- `ois/registries/base.py` — deterministic versioned registry primitive.
- `ois/registries/capability_registry.py` — capability registration.
- `ois/registries/agent_registry.py` — agent registration.
- `ois/registries/tool_registry.py` — tool/connector registration.
- `ois/registries/workflow_registry.py` — workflow registration.
- `ois/registries/model_registry.py` — model/provider registration.
- `ois/control_plane/controller.py` — control-plane boundary.
- `ois/kernel/supervisor.py` — supervision/delegation boundary.
- `ois/kernel/runtime.py` — execution boundary.

## Mapping rule

The Social Intelligence Fabric is a domain package **on top of OIS**, not a second application architecture.

| Social structure family | Existing OIS target |
|---|---|
| Intelligence/entity/audience/competitor/creative/content/SEO | Capability Registry + `CapabilityContract` |
| Social agents | Agent Registry + `AgentContract` |
| Platform connectors/external integrations | Tool Registry + `ToolContract` |
| Campaigns/workflows/scheduling | Workflow Registry + versioned workflow definitions |
| Model/provider abstractions | Model Registry |
| Approval/governance | Policy Engine |
| Content/quality gates | Validation Engine / `Validator` |
| Memory/patterns | Existing memory boundary |
| Analytics/attribution/prediction | Measurement boundary |
| Experiments/learning | Learning + Controlled Evolution |
| Retry/checkpoint/recovery | Existing recovery/checkpoint boundaries |
| Telemetry | Existing observability boundary |

## Contract rules

1. Stable IDs and explicit versions are mandatory.
2. Capability inputs/outputs remain typed through `CapabilityContract` schemas.
3. Agents declare tools and model requirements through `AgentContract`.
4. Tools declare side effects, network policy, secrets, approval and idempotency through `ToolContract`.
5. External publishing is policy-controlled and validation-gated.
6. Every action is correlated to `ExecutionIdentity` / `execution_id`.
7. Domain metadata is additive; the Kernel remains authoritative.
8. Learning creates evidence-backed candidates; it does not silently mutate production.
9. The inventory is a specification until implementations and tests promote entries to verified runtime capability.

## Inventory

`inventory.py` is the canonical machine-readable Python manifest and asserts that exactly **394 structures** are present. `integration_inventory.json` is the compact manifest pointing to it.

## Execution path

```text
Social request
  -> Control Plane
  -> Supervisor
  -> Workflow Registry
  -> Capability / Agent / Tool resolution
  -> Policy authorization
  -> Runtime
  -> Validation
  -> Checkpoint / Recovery
  -> Artifact + Evidence
  -> Measurement
  -> Learning
  -> Controlled Evolution
```

No new parallel Kernel, registry, or execution authority is introduced by this integration.
