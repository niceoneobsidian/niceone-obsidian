"""Kernel bindings for the Social Genome niche intelligence layer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .niche_genome import (
    NicheObservation,
    NodeKind,
    build_taxonomy_node,
    infer_intersection_edges,
    score_niche,
)


class NicheTaxonomyCapability:
    """Build a candidate macro/micro niche taxonomy without external side effects."""

    def __init__(self) -> None:
        self._contract = CapabilityContract(
            capability_id="social.genome.taxonomy.build",
            version="1.0.0",
            description="Build candidate Social Genome chromosome/gene taxonomy nodes.",
            input_schema={"nodes": "array"},
            output_schema={"nodes": "array", "intersection_edges": "array"},
            risk_level=RiskLevel.LOW,
            allowed_domains=("social_intelligence",),
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    @property
    def contract(self) -> CapabilityContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        raw_nodes = request.input.get("nodes", [])
        if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, str | bytes):
            raise TypeError("nodes must be a sequence")

        nodes = [
            build_taxonomy_node(
                node_id=str(item["node_id"]),
                name=str(item["name"]),
                kind=cast(NodeKind, str(item["kind"])),
                parent_id=item.get("parent_id"),
                description=str(item.get("description", "")),
                keywords=item.get("keywords", ()),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in raw_nodes
        ]
        edges = infer_intersection_edges(nodes)
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "nodes": [node.model_dump(mode="json") for node in nodes],
                "intersection_edges": [edge.model_dump(mode="json") for edge in edges],
            },
        )


class NicheScoringCapability:
    """Score a niche from supplied observations and an explicit demand signal."""

    def __init__(self) -> None:
        self._contract = CapabilityContract(
            capability_id="social.genome.niche.score",
            version="1.0.0",
            description="Compute deterministic, evidence-aware niche opportunity scores.",
            input_schema={
                "node_id": "string",
                "observations": "array",
                "demand_score": "number",
            },
            output_schema={"score": "object"},
            risk_level=RiskLevel.LOW,
            allowed_domains=("social_intelligence",),
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    @property
    def contract(self) -> CapabilityContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        node_id = str(request.input.get("node_id", "")).strip()
        raw_observations = request.input.get("observations", [])
        if not node_id:
            raise ValueError("node_id is required")
        if not isinstance(raw_observations, Sequence) or isinstance(raw_observations, str | bytes):
            raise TypeError("observations must be a sequence")

        observations = [NicheObservation.model_validate(item) for item in raw_observations]
        score = score_niche(
            node_id,
            observations,
            demand_score=float(request.input.get("demand_score", 0.0)),
        )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"score": score.model_dump(mode="json")},
        )


def register_niche_genome_capabilities(registry: CapabilityRegistry) -> None:
    """Bind Social Genome capabilities to the authoritative OIS registry."""
    registry.register(NicheTaxonomyCapability())
    registry.register(NicheScoringCapability())
