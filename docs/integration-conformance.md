# OIS Integration Conformance

`IntegrationConformance` is the canonical verification layer over the existing integration fabric.
It does not create a second provider registry, gateway, credential system, retry system, rate limiter, or evidence system.

## Discovery

SourceAdapterRegistry -> IntegrationConformance.discover() -> provider/spec inspection -> explicit evidence -> 23-column matrix

## Canonical matrix

PROVIDER | ADAPTER | REGISTRATION | CAPABILITY | TOOL | AUTH | CREDENTIAL | SCOPES | POLICY | RATE LIMIT | RETRY | TIMEOUT | IDEMPOTENCY | EVENTS | PROVENANCE | EVIDENCE | STRUCTURAL TEST | CONTRACT TEST | LIVE TEST | E2E TEST | NEGATIVE TEST | CI GATE | PRODUCTION VERIFICATION

Unknown is intentional. A registered adapter is not automatically live, E2E verified, or production verified.
Provider-specific evidence is supplied through a verifier and retained in the machine-readable report.

## Why this shape

The existing repository already has SourceAdapterRegistry, SourceGateway, centralized credential/authentication, rate limiting, idempotency, provenance, evidence, outbox, and opt-in live tests. The framework audits those boundaries rather than replacing them.

## Usage

from ois.integration_conformance import IntegrationConformance
report = IntegrationConformance(source_adapter_registry).audit()
print(report.to_json())

CI should fail only when a field declared mandatory by a provider policy is MISSING or UNKNOWN. Not every provider needs OAuth scopes, Tool Registry exposure, or production write access.