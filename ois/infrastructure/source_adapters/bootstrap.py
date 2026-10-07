"""Canonical application bootstrap for governed source adapters.

The conformance certificate must inspect the same SourceAdapterRegistry that
the application uses for source registration. This factory is the single
bootstrap boundary for registry construction; it does not discover sources
from repository text.
"""

from __future__ import annotations

from .base import SourceAdapterRegistry
from .sportmonks import SportmonksFootballAdapter


def build_application_source_adapter_registry() -> SourceAdapterRegistry:
    """Build the canonical application registry for governed source adapters."""
    registry = SourceAdapterRegistry()
    SportmonksFootballAdapter.register(registry)
    return registry
