# Phase C — OIS Intelligence Integration & Operations

Phase C turns canonical live-source events into governed OIS work.

## Components

- **SourceIntelligencePipeline** — policy authorization, intelligence delivery, and recovery.
- **SourcePolicyStore** — tenant/workspace/source policy enforcement.
- **DeadLetterStore / SourceRecovery** — bounded retry, dead-lettering, and replay.
- **SourceConfigurationService** — transport-neutral CRUD boundary for UI/API adapters.
- **CanonicalSourceEvent** — provider-neutral event contract.

## Runtime flow

External source -> Source Gateway -> Canonical Source Event -> Control Plane Source Policy -> Intelligence Handler -> recovery/dead-letter.

The configuration service intentionally does not depend on an HTTP framework. A REST, CLI, admin UI, or future Control Plane API can expose the same service without duplicating authorization rules.

## Security boundary

Source policy is evaluated with tenant and workspace scope. Source configuration never stores secret material; it stores only a credential reference. Authentication remains owned by the Credential & Auth Manager.

## Recovery

Processing is retried up to the configured maximum. Exhausted events are stored as dead letters with the original canonical event, reason, and attempt count. Successful replay removes the dead-letter record.

Production deployments should replace the in-memory policy/configuration/dead-letter stores with durable implementations while retaining these contracts.
