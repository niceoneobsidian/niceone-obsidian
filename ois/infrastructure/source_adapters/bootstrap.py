"""Canonical application bootstrap for governed source adapters.

The conformance certificate must inspect the same SourceAdapterRegistry that
the application uses for source registration. This factory is the single
bootstrap boundary for registry construction; it does not discover sources
from repository text.
"""

from __future__ import annotations

from ois.infrastructure.source_gateway.contracts import SourceSpec
from ois.integration.conformance_metadata import (
    ConformanceEvidence,
    ProviderConformanceMetadata,
)
from ois.integrations.github import GitHubSource
from ois.integrations.google import GoogleDriveSource
from ois.integrations.meta import MetaFacebookSource

from .base import SourceAdapterRegistry
from .sportmonks import SportmonksFootballAdapter


def _http_provider_conformance(
    source_id: str,
    source_path: str,
) -> ProviderConformanceMetadata:
    evidence = (source_path, "ois/infrastructure/source_adapters/http.py")
    return ProviderConformanceMetadata(
        source_id=source_id,
        claims={
            "ADAPTER": ConformanceEvidence(
                "IMPLEMENTED",
                (source_path,),
                "Provider implements the governed SourceAdapter ingest boundary.",
            ),
            "REGISTRATION": ConformanceEvidence(
                "IMPLEMENTED",
                ("ois/infrastructure/source_adapters/bootstrap.py",),
                "Provider is registered by the canonical application source registry.",
            ),
            "CAPABILITY": ConformanceEvidence(
                "IMPLEMENTED",
                ("ois/infrastructure/source_adapters/bootstrap.py",),
                "Provider capabilities are declared by its canonical SourceSpec.",
            ),
            "AUTH": ConformanceEvidence(
                "IMPLEMENTED",
                evidence,
                "Provider authentication is bound to HttpSourceAdapter and SourceGateway "
                "credential handling.",
            ),
            "CREDENTIAL": ConformanceEvidence(
                "IMPLEMENTED",
                evidence,
                "Credential references are resolved through the governed SourceGateway boundary.",
            ),
            "TIMEOUT": ConformanceEvidence(
                "IMPLEMENTED",
                evidence,
                "HttpSourceAdapter requires a positive timeout and passes it to "
                "urllib request execution.",
            ),
            "PROVENANCE": ConformanceEvidence(
                "IMPLEMENTED",
                ("ois/infrastructure/source_gateway/contracts.py",),
                "SourceProvenance is part of the governed source gateway contract.",
            ),
            "EVIDENCE": ConformanceEvidence(
                "IMPLEMENTED",
                ("ois/infrastructure/source_gateway/gateway.py",),
                "SourceGateway commits canonical raw evidence for source observations.",
            ),
            "STRUCTURAL TEST": ConformanceEvidence(
                "TESTED",
                ("tests/integration_conformance/test_repository_certificate_cli_contract.py",),
                "Canonical registry structure and certificate integration are structurally tested.",
            ),
            "CONTRACT TEST": ConformanceEvidence(
                "TESTED",
                ("tests/integrations/test_phase_a_sources.py",),
                "Provider source contracts are covered by the Phase A integration tests.",
            ),
            "CI GATE": ConformanceEvidence(
                "TESTED",
                (".github/workflows/p0-conformance.yml",),
                "The canonical provider registry is exercised by the repository P0 conformance gate.",
            ),
        },
    )


def build_application_source_adapter_registry() -> SourceAdapterRegistry:
    """Build the canonical registry for structurally governed source adapters."""
    registry = SourceAdapterRegistry()

    registry.register(
        GitHubSource(),
        SourceSpec(
            source_id=GitHubSource.source_id,
            provider="github",
            protocol="rest",
            version="v3",
            capabilities=("github.user", "evidence.raw"),
        ),
        conformance=_http_provider_conformance(
            GitHubSource.source_id,
            "ois/integrations/github/source.py",
        ),
    )
    registry.register(
        GoogleDriveSource(),
        SourceSpec(
            source_id=GoogleDriveSource.source_id,
            provider="google",
            protocol="rest",
            version="v3",
            capabilities=("google.drive.files", "evidence.raw"),
        ),
        conformance=_http_provider_conformance(
            GoogleDriveSource.source_id,
            "ois/integrations/google/source.py",
        ),
    )
    registry.register(
        MetaFacebookSource(),
        SourceSpec(
            source_id=MetaFacebookSource.source_id,
            provider="meta",
            protocol="rest",
            version="v24.0",
            capabilities=("meta.graph.me", "evidence.raw"),
        ),
        conformance=_http_provider_conformance(
            MetaFacebookSource.source_id,
            "ois/integrations/meta/source.py",
        ),
    )

    sportmonks = SportmonksFootballAdapter()
    registry.register(
        sportmonks,
        sportmonks.spec(),
        conformance=ProviderConformanceMetadata(
            source_id=sportmonks.source_id,
            claims={
                "ADAPTER": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_adapters/sportmonks.py",),
                    "Sportmonks implements the governed SourceAdapter ingest boundary.",
                ),
                "REGISTRATION": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_adapters/bootstrap.py",),
                    "Sportmonks is registered by the canonical application source registry.",
                ),
                "CAPABILITY": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_adapters/sportmonks.py",),
                    "Sportmonks declares football and raw-evidence capabilities in SourceSpec.",
                ),
                "AUTH": ConformanceEvidence(
                    "IMPLEMENTED",
                    (
                        "ois/infrastructure/source_adapters/sportmonks.py",
                        "ois/infrastructure/source_adapters/http.py",
                    ),
                    "Sportmonks uses API-key authentication through the governed HTTP "
                    "adapter and SourceGateway.",
                ),
                "CREDENTIAL": ConformanceEvidence(
                    "IMPLEMENTED",
                    (
                        "ois/infrastructure/source_adapters/sportmonks.py",
                        "ois/infrastructure/source_gateway/credentials.py",
                    ),
                    "Sportmonks requires a credential reference and resolves it through "
                    "the governed gateway.",
                ),
                "TIMEOUT": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_adapters/sportmonks.py",),
                    "Sportmonks exposes a positive HTTP timeout through its adapter constructor.",
                ),
                "PROVENANCE": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_gateway/contracts.py",),
                    "SourceProvenance is part of the governed source gateway contract.",
                ),
                "EVIDENCE": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_gateway/gateway.py",),
                    "SourceGateway commits canonical raw evidence for Sportmonks observations.",
                ),
                "STRUCTURAL TEST": ConformanceEvidence(
                    "TESTED",
                    ("tests/integration_conformance/test_repository_certificate_cli_contract.py",),
                    "Canonical registry structure and certificate integration are structurally tested.",
                ),
                "CONTRACT TEST": ConformanceEvidence(
                    "TESTED",
                    ("tests/infrastructure/test_sportmonks_adapter.py",),
                    "Sportmonks adapter behavior is covered by its infrastructure contract tests.",
                ),
                "CI GATE": ConformanceEvidence(
                    "TESTED",
                    (".github/workflows/p0-conformance.yml",),
                    "Sportmonks participates in the repository P0 conformance gate.",
                ),
            },
        ),
    )

    return registry
