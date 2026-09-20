# Health, readiness, and observability

## Health contract

A health check answers whether the process is alive. It should be cheap, dependency-light, and free of credentials or sensitive payloads.

## Readiness contract

Readiness answers whether the service may receive work. It should verify the dependencies required for safe execution, including database connectivity, migration compatibility, required configuration, and telemetry availability. A service that cannot authorize, persist state, or append evidence should not report ready for consequential work.

## Required signals

At minimum, capture structured metrics or events for:

- Execution attempts, successes, failures, and terminal states.
- Authorization decisions and denials.
- Duplicate deliveries and idempotency hits.
- State-transition rejections.
- Recovery decisions by type and attempt number.
- Evidence append failures.
- Validation outcomes.
- Latency by execution phase.
- External call timeout and retry counts.
- Database and Redis dependency health.

## Trace and log rules

Use a stable execution identifier and propagate it through planning, authorization, execution, validation, persistence, and recovery. Logs should be structured and correlated. Do not log secrets, credentials, authorization tokens, or unrestricted model prompts and outputs.

## Alerts

Alert on:

- Readiness loss.
- Repeated authorization failures.
- Evidence append failures.
- Invalid state-transition spikes.
- Recovery escalation or retry exhaustion.
- Duplicate delivery anomalies.
- Dependency saturation or elevated latency.

## Evidence review

Operational dashboards are not a substitute for durable execution evidence. A production claim requires implementation, tests, integration, runtime, security, observability, recovery, deployment, rollback, and operational verification evidence.
