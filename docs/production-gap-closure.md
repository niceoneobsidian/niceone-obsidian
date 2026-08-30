# Production Gap Closure

This branch adds executable control primitives for the gaps identified by the OIS architecture review.

| Gap | Implemented here | Still requires environment evidence |
|---|---|---|
| Production deployment | Versioned deployment/activation controller with approval + evidence | Real cloud/cluster deployment target, secrets, health checks, release pipeline |
| Production activation | Explicit approval/evidence gate | Production environment and operator approval |
| Rollback | Versioned rollback controller and rollback records | Real deployment adapter + restore/drain validation |
| Canary evolution | Deterministic assignment + metric-gated promote/rollback | Real traffic router, telemetry source, sustained canary experiment |
| Distributed orchestration | SQLite-backed worker leases and idempotent result storage | Shared production database, worker fleet, fencing/heartbeat strategy |
| External connectors | HTTPS-only connector boundary | Platform-specific adapters, OAuth/API credentials, scopes, rate limits and live integration tests |
| Enterprise RBAC/ABAC | Deny-by-default role/attribute authorization primitive | Identity provider integration, policy administration, audit retention and tenant isolation tests |
| Semantic world | Durable SQLite entities/facts with provenance and append-only fact versions | Production graph/vector stores, ingestion connectors, conflict resolution and scale testing |
| Learning loop | Evidence-gated propose/evaluate/approve/activate lifecycle | Production telemetry, attribution, replay corpus, statistical evaluation and automated rollback |
| End-to-end operation | Components are individually executable and testable | Integrated deployment, runtime, security, observability, recovery and operational evidence |

## Required activation sequence

1. Run the repository verification suite.
2. Provision a production database and identity provider.
3. Configure platform connector adapters and credentials through the deployment secret manager.
4. Deploy a versioned release to staging.
5. Run integration, security, recovery and performance checks.
6. Start a 5% canary.
7. Require measured success and latency thresholds before promotion.
8. Record the deployment/canary evidence.
9. Promote only through the governed activation boundary.
10. Exercise rollback against the live deployment target and retain the evidence.

The implementation intentionally does **not** fabricate cloud resources, credentials, third-party API access, or production runtime results. Those are external prerequisites for the remaining production-verification state.
