# OIS Integration Conformance

IntegrationConformance is the canonical verification layer over the existing integration fabric. It does not create a second provider registry, gateway, credential system, retry system, rate limiter, or evidence system.

## Three evidence layers

### 1. Runtime registry conformance

IntegrationConformance consumes the existing SourceAdapterRegistry and emits the exact 23-column matrix:

PROVIDER | ADAPTER | REGISTRATION | CAPABILITY | TOOL | AUTH | CREDENTIAL | SCOPES | POLICY | RATE LIMIT | RETRY | TIMEOUT | IDEMPOTENCY | EVENTS | PROVENANCE | EVIDENCE | STRUCTURAL TEST | CONTRACT TEST | LIVE TEST | E2E TEST | NEGATIVE TEST | CI GATE | PRODUCTION VERIFICATION

Unknown is intentional. A registered adapter is not automatically live, E2E verified, or production verified.

### 2. Explicit provider conformance metadata

Canonical source registrations may attach `ProviderConformanceMetadata` to the same `SourceAdapterRegistry` entry. Each claim names a 23-column dimension, a conformance status, and repository-relative evidence paths. This is the explicit contract for dimensions that cannot safely be inferred from generic adapter structure.

Metadata is evidence-backed and immutable. Positive claims must include evidence paths, and the repository certificate verifies those paths exist inside the repository. Metadata cannot claim live, E2E, or production verification; those statuses require runtime/CI proof. This keeps static provider declarations from becoming false production readiness signals.

For the current canonical Phase-A sources, metadata explicitly declares authentication, credential binding, and timeout behavior. Scopes, policy, retry, rate-limit, idempotency, event, live, E2E, negative, and production dimensions remain UNKNOWN until their own evidence contracts are implemented.

### 3. Repository-wide certificate

ois.integration.repository_certificate binds the matrix to repository evidence:

- provider/source adapter implementation
- explicit provider conformance metadata and its evidence paths
- registry and SourceSpec evidence
- authentication and credential paths
- scopes
- policy/configuration evidence
- gateway reliability controls
- structural/contract/live/E2E/negative tests
- CI workflows
- production-readiness manifests

The certificate is content-hashed and includes the commit SHA used to build it. It is fail-closed for the mandatory policy dimensions.

Run locally:

python -m ois.integration.repository_certificate --root . --commit <sha> --output integration-conformance-certificate.json

Add --strict for a promotion gate. Without --strict, the command produces the certificate even when the repository has conformance gaps; this is intentional so the gaps are observable rather than hidden.

## Evidence rules

A repository file is evidence of implementation or test coverage only when it is connected to the discovered provider/source ID. Generic architecture prose cannot promote a provider to live or production verified.

Production verification requires explicit evidence. A production-readiness manifest containing production_verified: false cannot promote the certificate.

Synthetic adapters may exercise contracts but cannot establish production verification.

## CI

The canonical GitHub Actions workflow runs the conformance tests and publishes the repository-wide certificate as a workflow artifact. GitHub documents artifacts as the mechanism for retaining build/test output after a workflow run, and required status checks can be used to block protected-branch merges when a gate is promoted to required.

The workflow currently has contents: read, following GitHub's least-privilege guidance for GITHUB_TOKEN.

For a production gate, make the conformance job a required status check on the protected branch. GitHub requires the required check to succeed for the latest commit before merge.

Contract tests and E2E tests remain distinct evidence classes: contract tests validate an external boundary, while E2E tests validate the system as a whole.
