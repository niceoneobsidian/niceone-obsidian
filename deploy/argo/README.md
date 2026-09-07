# OIS Kernel Canary Cutover

This directory defines the evidence-gated production activation boundary for the OIS kernel workers.

## Activation sequence

```text
build artifact
  -> deploy Rollout
  -> 10% canary
  -> 5m pause
  -> Prometheus Analysis
  -> 50% canary
  -> 5m pause
  -> Prometheus Analysis
  -> 100% promotion
```

Argo Rollouts owns traffic routing and rollback. The Python monitor is observational: it records a hash-linked forensic evidence artifact and exits non-zero on `Degraded`, `Aborted`, or timeout. It does not independently promote traffic.

## Telemetry contract

The worker telemetry must expose the following Prometheus labels consistently:

- `service`: the canary service identity supplied to the AnalysisTemplate
- `status`: HTTP/status-class label for request outcomes
- `to_state`: destination workflow state for workflow transitions

Required metrics:

- `http_requests_total`
- `ois_workflow_state_transitions_total`
- `ois_worker_panics_total`

`ois_worker_panics_total` must increment only for an actual worker panic/crash condition. A missing metric is treated as inconclusive by the AnalysisTemplate rather than being converted into a fabricated zero.

## Safety boundaries

- No LLM output controls rollout traffic.
- No promotion is authorized by the Python monitor.
- Analysis failure is delegated to Argo Rollouts, which owns the canary state transition.
- Evidence written by `argo_canary_gate.py` is a forensic artifact for ingestion into the canonical OIS evidence ledger; it is not itself the durable production ledger.
- The production environment must provide the Prometheus service DNS configured in `ois-analysis-template.yaml`, or the manifest must be changed through the normal versioned deployment process.

## Important integration requirement

The supplied repository did not previously demonstrate production telemetry labels or a live cluster binding. Therefore this package is **IMPLEMENTED as deployment configuration and monitoring code**, but it is not **PRODUCTION VERIFIED** until the staging cluster proves:

1. real canary traffic reaches the canary service;
2. all three safety metrics are populated for that traffic;
3. a forced analysis failure causes an Argo rollback;
4. a healthy canary reaches promotion;
5. the evidence artifact is ingested into the durable OIS evidence ledger;
6. the resulting deployment, artifact digest, rollout revision, test run, and evidence IDs are cryptographically bound.
