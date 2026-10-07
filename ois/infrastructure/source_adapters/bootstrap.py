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

from .base import SourceAdapterRegistry
from .sportmonks import SportmonksFootballAdapter


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
    )
    SportmonksFootballAdapter.register(registry)

    return registry
