# P1 Production Operations Runbook

## Scope

P1 adds additive operational assets for high-throughput load, controlled database chaos, and Prometheus/Grafana observability. It does not declare production readiness by file presence.

## Safety gates

- Run Locust only against an isolated staging environment.
- Supply synthetic tenant IDs and test-only tokens through environment variables.
- Chaos is disabled by default and must be enabled only in an authorized test environment.
- Execute one fault class at a time before combined experiments.
- Capture execution IDs, trace IDs, checkpoint IDs, failure classifications, retry counts, recovery actions, and final outcomes.

## Load test

```bash
OIS_STRESS_TENANTS="tenant-a,tenant-b,tenant-c" \
OIS_STRESS_TOKEN_PREFIX="staging-token-" \
OIS_TEST_RUN_ID="p1-$(date +%s)" \
locust -f ops/p1/loadtest/locustfile_high_throughput.py \
  --host http://staging-uis --users 250 --spawn-rate 25 --run-time 10m
```

Record p50/p95/p99 latency, throughput, 4xx/5xx, 423 contention, DB-pool saturation, Redis latency, worker utilization and checkpoint latency.

## Chaos

Inject network-reset and delayed-database faults through the interceptor at controlled probability. Verify bounded retry/recovery, durable checkpoint behavior, lock release, tenant isolation, and final state consistency. The interceptor must be wired into the application's existing DB/checkpoint dependency boundary before this becomes an integration test.

## Dashboard

Import `ops/p1/observability/grafana/ois_p1_operations.json`. Replace `${DS_PROMETHEUS}` with the provisioned Prometheus datasource variable/UID. Verify the metric names and label cardinality against the deployed P0.6 telemetry before relying on the panels.

## Promotion gate

P1 is **IMPLEMENTED/CONFIGURED** after code and dashboard validation. It becomes **TESTED/INTEGRATED** only after real staging load and chaos runs produce evidence. It becomes **PRODUCTION VERIFIED** only after security, recovery, performance, deployment and rollback evidence satisfy the OIS readiness gates.
