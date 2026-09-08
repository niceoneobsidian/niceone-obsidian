"""Declarative sovereign provider registry metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    name: str
    role: str
    authority: str
    activation: str


SOVEREIGN_PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("postgresql", "canonical state", "ois", "active"),
    ProviderSpec("langgraph", "agent orchestration", "ois", "active-adapter"),
    ProviderSpec("temporal", "durable workflow candidate", "ois", "evaluation"),
    ProviderSpec("mcp", "tool protocol", "ois", "governed-adapter"),
    ProviderSpec("n8n", "integration execution", "ois", "governed-adapter"),
    ProviderSpec("supabase-patterns", "security patterns", "ois", "pattern-only"),
    ProviderSpec("dify", "reference platform", "ois", "reference-only"),
    ProviderSpec("flowise", "visual workflow reference", "ois", "reference-only"),
)
