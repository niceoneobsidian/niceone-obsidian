# OIS Kernel Core Helm Chart

This chart packages the OIS deployment boundary for the Kernel supervisor and CRD controller.

## Deployment contract

1. The PostgreSQL secret named by `database.secretName` must already exist in the target namespace.
2. The schema migration Job runs as a Helm `pre-install,pre-upgrade` hook and must complete before the release proceeds.
3. The `SandboxGuard` CRD must be installed before the CRD controller is activated.
4. Vault Agent Injector must be installed and configured when `vault.enabled=true`.
5. The configured images must already exist in the private registry.
6. `runtimeClassName` should only be set when the cluster has the corresponding RuntimeClass installed.

## Security boundary

The chart uses non-root containers, drops Linux capabilities, disables privilege escalation, and makes the root filesystem read-only. Database credentials are referenced from a Kubernetes Secret; the chart does not embed credentials.

The supervisor is authorized through the OIS service account and RBAC policy. Deployment authorization remains a Control Plane responsibility.

## Evidence boundary

A successful Helm render/lint is deployment-manifest evidence only. It does not establish runtime, security, multi-tenant, performance, or production verification. Those claims require the corresponding OIS integration and operational evidence gates.
