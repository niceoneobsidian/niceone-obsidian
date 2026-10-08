# Design Intelligence → OIS Execution Spine

## Canonical boundary

Design Intelligence is a domain capability layer inside OIS. It does not own policy, execution, checkpointing, idempotency, recovery, or evidence storage.

```text
Design objective
      ↓
OIS Design Intelligence catalog
      ↓
OIS Capability Registry
      ↓
OIS Policy / Authorization
      ↓
OIS ExecutionRuntime
      ↓
DesignCapabilityFabric
      ↓
Bound design provider
      ↓
OIS output validation
      ↓
OIS checkpoint / idempotency / evidence
```

## Integration points

- `ois/design_intelligence/catalog.py` remains the design domain catalog.
- `ois/design_intelligence/kernel_integration.py` converts each catalog entry into an OIS `CapabilityContract` and registers it in the canonical `CapabilityRegistry`.
- `ois/design_intelligence/fabric.py` remains the provider boundary. Providers are explicitly bound to capability IDs.
- `ois/design_intelligence/integration.py` exposes `DesignOISRuntime`, a convenience entry point backed by `OISSpine`.
- `ois/kernel/runtime.py` remains the only execution authority.

## Provider state is explicit

Registration does not imply an implemented provider. An unbound design capability returns `DesignProviderUnavailable` rather than silently pretending to have produced an artifact. This preserves OIS evidence discipline.

A provider is bound explicitly:

```python
runtime.fabric.register_provider("brand.identity", provider)
```

The provider then executes behind the existing OIS policy, validation, checkpoint, idempotency, recovery, and evidence lifecycle.

## Verification

The integration test suite verifies:

1. all 17 design capabilities are registered in the canonical OIS registry;
2. a bound `brand.identity` provider executes through `ExecutionRuntime`;
3. authorization and capability-completion evidence are emitted;
4. an unbound design provider fails explicitly;
5. `DesignOISRuntime` enters through `OISSpine` and emits spine evidence.

This establishes the architectural vertical slice. It does not claim that all 17 design capabilities have production providers; provider implementation and production verification remain separate evidence states.