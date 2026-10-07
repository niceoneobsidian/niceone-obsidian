"""Canonical provider capability contracts for governed external sources."""

from __future__ import annotations

from ois.kernel.contracts import CapabilityContract
from ois.kernel.types import RiskLevel, SideEffectLevel
from ois.registries.capability_registry import CapabilityRegistry

PROVIDER_CAPABILITIES = (
    CapabilityContract(
        capability_id="provider.github.rest.user",
        version="1.0.0",
        description="Read the authenticated GitHub user through the governed source gateway.",
        permissions=("github.read",),
        allowed_domains=("integration",),
        risk_level=RiskLevel.LOW,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        timeout_seconds=30.0,
        max_retries=3,
    ),
    CapabilityContract(
        capability_id="provider.google.drive.files",
        version="1.0.0",
        description="Read Google Drive file metadata through the governed source gateway.",
        permissions=("google.drive.read",),
        allowed_domains=("integration",),
        risk_level=RiskLevel.LOW,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        timeout_seconds=30.0,
        max_retries=3,
    ),
    CapabilityContract(
        capability_id="provider.meta.graph.me",
        version="1.0.0",
        description="Read the authenticated Meta profile through the governed source gateway.",
        permissions=("meta.read",),
        allowed_domains=("integration",),
        risk_level=RiskLevel.LOW,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        timeout_seconds=30.0,
        max_retries=3,
    ),
    CapabilityContract(
        capability_id="provider.tiktok.display.v2",
        version="1.0.0",
        description="Read TikTok display data through the governed source gateway.",
        permissions=("tiktok.read",),
        allowed_domains=("integration",),
        risk_level=RiskLevel.LOW,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        timeout_seconds=30.0,
        max_retries=3,
    ),
    CapabilityContract(
        capability_id="provider.rss.news",
        version="1.0.0",
        description="Read public RSS/news feeds into tenant-scoped evidence.",
        permissions=("research.read",),
        allowed_domains=("research",),
        risk_level=RiskLevel.LOW,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        timeout_seconds=30.0,
        max_retries=3,
    ),
    CapabilityContract(
        capability_id="provider.sportmonks.football.v3",
        version="1.0.0",
        description="Read Sportmonks football data through the governed source gateway.",
        permissions=("football.read",),
        allowed_domains=("football", "integration"),
        risk_level=RiskLevel.LOW,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        timeout_seconds=30.0,
        max_retries=3,
    ),
)


def build_provider_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for contract in PROVIDER_CAPABILITIES:
        registry.register(contract.capability_id, contract.version, contract)
    return registry
