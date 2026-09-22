# Operability

## Health model

A deployment should expose liveness, readiness, dependency health, execution health, and evidence-write health.

## Minimum telemetry

Track privacy-safe references for execution/run ID, tenant, capability/version, state transition, authorization decision, lease epoch, idempotency reference, latency, retry/recovery outcome, persistence failures, and side-effect outcome.

Never log secrets, credentials, authorization tokens, or unnecessary personal data.

## Alerts

Alert on repeated authorization failures, persistence errors, lease fencing rejections, stale-worker mutations, queue growth, repeated recovery loops, readiness failures, and evidence-write failures.

## Operational evidence

A release should retain enough evidence to reconstruct what version ran, what dependencies were used, and whether critical authorization, persistence, and recovery invariants were exercised.
