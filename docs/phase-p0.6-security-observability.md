# P0.6 — Security + Observability Hardening

## Implemented on branch

`phase-p0.6-security-observability`

## Security boundary

The worker deployment uses the Vault Agent Injector rather than Kubernetes Secret environment variables. The worker receives:

- dynamic PostgreSQL credentials from `database/creds/ois-tenant-pool`;
- read-only supervisor signing material from `secret/data/ois/kernel/signing`;
- rendered files under `/vault/secrets` with mode `0400`;
- a non-root, non-privileged runtime with all Linux capabilities dropped;
- the existing gVisor runtime class boundary.

Vault Agent Injector renders requested secrets into a shared memory volume, so the application does not need direct Vault credentials. The sidecar remains enabled so leases can be renewed and templates can be re-rendered. Application-level database pooling must still handle credential rotation correctly; a process restart/reconnect policy is required if a pool cannot refresh credentials from the rendered files.

## Observability boundary

The supervisor now accepts `SupervisorExecutionTracker` and wraps both direct capability execution and plan execution in OpenTelemetry spans.

Telemetry flow:

```text
OIS Supervisor
    ↓ OTLP/gRPC
OpenTelemetry Collector
    ├── traces → Tempo
    └── metrics → Prometheus exporter → Prometheus scrape
```

Metrics deliberately exclude `tenant_id` and `thread_id` labels to prevent unbounded cardinality. Traces use a tenant fingerprint rather than the raw tenant identifier.

Implemented measurements:

- `ois_workflow_state_transitions_total`
- `ois_workflow_executions_total`
- `ois_workflow_execution_duration_seconds`
- `ois_hitl_human_latency_seconds`

## Runtime bootstrap

Production workers should initialize telemetry before constructing supervisors:

```python
from production.telemetry import (
    initialize_production_telemetry,
    shutdown_production_telemetry,
)

tracker = initialize_production_telemetry()
supervisor = Supervisor(..., telemetry=tracker)

# On graceful process shutdown:
shutdown_production_telemetry()
```

## Required external configuration

The following remain deployment prerequisites rather than claims of repository-local activation:

1. Vault Kubernetes auth must bind `ois-worker-sa` in `ois-worker-sandbox` to `ois-tenant-worker-role`.
2. The Vault database secrets engine must expose `database/creds/ois-tenant-pool`.
3. The KV signing secret must exist at `secret/data/ois/kernel/signing`.
4. The Vault Agent Injector admission webhook must be installed and healthy.
5. The OpenTelemetry Collector must be deployed using `production/observability/otel-collector.yaml`.
6. Tempo and Prometheus endpoints must exist at the configured service names.
7. OTLP transport must use TLS in production; the checked-in `insecure: true` setting is intended only for an internal development/test collector and must be overridden for a production trust boundary.

## Evidence status

| Component | Status |
|---|---|
| Vault worker manifest | IMPLEMENTED / CONFIGURED |
| Least-privilege Vault policy | IMPLEMENTED / CONFIGURED |
| OTel supervisor instrumentation | IMPLEMENTED |
| OTLP collector pipeline | CONFIGURED |
| Prometheus scrape configuration | CONFIGURED |
| Runtime deployment of Vault | UNKNOWN until cluster evidence exists |
| Runtime deployment of Collector/Tempo/Prometheus | UNKNOWN until cluster evidence exists |
| End-to-end telemetry delivery | UNKNOWN until runtime test exists |
| Secret lease rotation under live workload | UNKNOWN until runtime test exists |
| Production TLS configuration | REQUIRED EXTERNAL CONFIGURATION |

P0.6 therefore establishes the code/configuration boundary without falsely promoting the system to production-verified status.
