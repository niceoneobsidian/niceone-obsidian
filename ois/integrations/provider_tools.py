"""Provider tool metadata bound to the canonical ToolRegistry.

Executable network I/O remains owned by SourceAdapterRegistry/SourceGateway.
These ToolRegistry entries are the governed discovery and authorization surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from ois.kernel.contracts import ToolContract
from ois.kernel.types import RiskLevel, SideEffectLevel
from ois.registries.tool_registry import ToolRegistry


@dataclass(frozen=True)
class ProviderToolDescriptor:
    contract: ToolContract
    source_id: str


PROVIDER_TOOLS = (
    ProviderToolDescriptor(
        ToolContract(
            capability_id="provider.github.rest.user",
            version="1.0.0",
            description="Governed read-only GitHub user source.",
            permissions=("github.read",),
            allowed_domains=("integration",),
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_retries=3,
            network_policy={"allowlist": ["api.github.com"]},
            secrets_required=("GITHUB_CREDENTIAL_REF",),
        ),
        "github.rest.user",
    ),
    ProviderToolDescriptor(
        ToolContract(
            capability_id="provider.google.drive.files",
            version="1.0.0",
            description="Governed read-only Google Drive file source.",
            permissions=("google.drive.read",),
            allowed_domains=("integration",),
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_retries=3,
            network_policy={"allowlist": ["www.googleapis.com"]},
            secrets_required=("GOOGLE_CREDENTIAL_REF",),
        ),
        "google.drive.files",
    ),
    ProviderToolDescriptor(
        ToolContract(
            capability_id="provider.meta.graph.me",
            version="1.0.0",
            description="Governed read-only Meta profile source.",
            permissions=("meta.read",),
            allowed_domains=("integration",),
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_retries=3,
            network_policy={"allowlist": ["graph.facebook.com"]},
            secrets_required=("META_CREDENTIAL_REF",),
        ),
        "meta.graph.me",
    ),
    ProviderToolDescriptor(
        ToolContract(
            capability_id="provider.tiktok.display.v2",
            version="1.0.0",
            description="Governed read-only TikTok display source.",
            permissions=("tiktok.read",),
            allowed_domains=("integration",),
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_retries=3,
            network_policy={"allowlist": ["open.tiktokapis.com"]},
            secrets_required=("TIKTOK_CREDENTIAL_REF",),
        ),
        "tiktok.display.v2",
    ),
    ProviderToolDescriptor(
        ToolContract(
            capability_id="provider.rss.news",
            version="1.0.0",
            description="Governed public RSS/news source.",
            permissions=("research.read",),
            allowed_domains=("research",),
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_retries=3,
        ),
        "rss.news",
    ),
    ProviderToolDescriptor(
        ToolContract(
            capability_id="provider.sportmonks.football.v3",
            version="1.0.0",
            description="Governed read-only Sportmonks football source.",
            permissions=("football.read",),
            allowed_domains=("football", "integration"),
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_retries=3,
            network_policy={"allowlist": ["api.sportmonks.com"]},
            secrets_required=("SPORTMONKS_CREDENTIAL_REF",),
        ),
        "sportmonks:football:v3",
    ),
)


def build_provider_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for descriptor in PROVIDER_TOOLS:
        registry.register(
            descriptor.contract.capability_id,
            descriptor.contract.version,
            descriptor,
            metadata={
                "source_id": descriptor.source_id,
                "authority": "SourceAdapterRegistry",
            },
        )
    return registry
