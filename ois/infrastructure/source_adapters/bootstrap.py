"""Canonical application bootstrap for governed source adapters.

The conformance certificate must inspect the same SourceAdapterRegistry that
the application uses for source registration. This factory is the single
bootstrap boundary for registry construction; it does not discover sources
from repository text.
"""

from __future__ import annotations

from ois.infrastructure.source_gateway.contracts import SourceSpec
from ois.integrations.github import GitHubSource
from ois.integrations.google import GoogleDriveSource
from ois.integrations.meta import MetaFacebookSource
from ois.integration.conformance_metadata import (
    ConformanceEvidence,
    ProviderConformanceMetadata,
)

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
            "AUTH": ConformanceEvidence(
                "IMPLEMENTED",
                evidence,
                "Provider authentication is bound to HttpSourceAdapter and SourceGateway credential handling.",
            ),
            "CREDENTIAL": ConformanceEvidence(
                "IMPLEMENTED",
                evidence,
                "Credential references are resolved through the governed SourceGateway boundary.",
            ),
            "TIMEOUT": ConformanceEvidence(
                "IMPLEMENTED",
                evidence,
                "HttpSourceAdapter requires a positive timeout and passes it to urllib request execution.",
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
                "AUTH": ConformanceEvidence(
                    "IMPLEMENTED",
                    (
                        "ois/infrastructure/source_adapters/sportmonks.py",
                        "ois/infrastructure/source_adapters/http.py",
                    ),
                    "Sportmonks uses API-key authentication through the governed HTTP adapter and SourceGateway.",
                ),
                "CREDENTIAL": ConformanceEvidence(
                    "IMPLEMENTED",
                    (
                        "ois/infrastructure/source_adapters/sportmonks.py",
                        "ois/infrastructure/source_gateway/credentials.py",
                    ),
                    "Sportmonks requires a credential reference and resolves it through the governed gateway.",
                ),
                "TIMEOUT": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/infrastructure/source_adapters/sportmonks.py",),
                    "Sportmonks exposes a positive HTTP timeout through its adapter constructor.",
                ),
            },
        ),
    )

    return registry
