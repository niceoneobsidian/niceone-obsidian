# Deployment guide

## Status

This document defines the deployment contract and checklist. It is not evidence that a production deployment currently exists. The repository is under controlled implementation.

## Required inputs

A deployment must identify:

- Git commit or immutable release tag.
- Python/runtime version.
- PostgreSQL version and migration level.
- Redis version and usage.
- Configuration source and secret manager.
- Observability destination.
- Operator and rollback owner.

## Pre-deployment checklist

- [ ] CI checks are green for the exact commit.
- [ ] Security and dependency scans are green.
- [ ] Database migrations are reviewed and reversible or have a documented forward-recovery plan.
- [ ] Authorization, idempotency, recovery, and evidence tests cover the change.
- [ ] Backups and restore verification are current.
- [ ] Health and readiness checks are available.
- [ ] Rollback criteria and owner are recorded.

## Deployment sequence

1. Build from the immutable commit or release tag.
2. Generate and retain build metadata and dependency evidence.
3. Verify configuration without printing secret values.
4. Apply migrations using the documented migration runner.
5. Start the application in a non-serving or draining mode.
6. Verify database connectivity, Redis connectivity, health, readiness, and telemetry.
7. Enable traffic gradually.
8. Observe error rate, latency, recovery activity, state-transition failures, and evidence-write failures.
9. Record the deployment result and evidence location.

## Go/no-go criteria

Do not activate a deployment if migrations fail, readiness is false, authorization checks are bypassed, evidence writes fail, or rollback cannot be executed.

## Configuration rules

- Keep secrets outside the repository.
- Use least-privilege database and Redis credentials.
- Separate development, staging, and production values.
- Fail closed when required authorization or configuration is missing.
- Do not log credentials, tokens, prompts containing secrets, or full external payloads by default.

## Post-deployment verification

Run a harmless end-to-end execution, verify its evidence, confirm duplicate delivery behavior, and check that dashboards and alerts receive telemetry. Record the commit, environment, result, and operator.
