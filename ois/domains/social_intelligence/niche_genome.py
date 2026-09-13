"""Governed Social Genome / niche intelligence primitives.

The Social Genome is a semantic layer over the existing Social Intelligence
Fabric. It models macro topics as chromosomes, concrete niches as genes, and
cross-niche relationships as edges. The module is intentionally provider- and
storage-neutral: persistence belongs to the OIS data plane and execution is
still governed by the existing registries and policy engine.

Evidence states are explicit. A generated taxonomy is a candidate until it is
supported by observations/evidence and validated by the OIS promotion gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field


NodeKind = Literal["chromosome", "gene", "topic", "community", "entity"]
EdgeKind = Literal["contains", "intersects", "related", "competes", "audience_overlap", "content_overlap"]
EvidenceStatus = Literal["candidate", "observed", "validated", "deprecated"]


class NicheNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    slug: str
    name: str
    kind: NodeKind
    parent_id: str | None = None
    description: str = ""
    keywords: tuple[str, ...] = ()
    audience_segments: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    language: str | None = None
    evidence_status: EvidenceStatus = "candidate"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    observation_count: int = Field(default=0, ge=0)


class NicheEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_node_id: str
    target_node_id: str
    kind: EdgeKind
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class NicheObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    node_id: str
    source_id: str
    platform: str
    observed_at: str
    engagement_rate: float = Field(default=0.0, ge=0.0)
    viral_velocity: float = Field(default=0.0, ge=0.0)
    sentiment_index: float = Field(default=0.0, ge=-1.0, le=1.0)
    content_count: int = Field(default=1, ge=1)
    evidence_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, object] = Field(default_factory=dict)


class NicheScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    demand_score: float = Field(ge=0.0, le=1.0)
    engagement_score: float = Field(ge=0.0, le=1.0)
    velocity_score: float = Field(ge=0.0, le=1.0)
    evidence_score: float = Field(ge=0.0, le=1.0)
    opportunity_score: float = Field(ge=0.0, le=1.0)
    sample_size: int = Field(ge=0)
    method_version: str = "social-genome.score.v1"


@dataclass(frozen=True)
class GenomeConfig:
    """Weights for deterministic niche opportunity scoring."""

    demand_weight: float = 0.30
    engagement_weight: float = 0.25
    velocity_weight: float = 0.25
    evidence_weight: float = 0.20

    def __post_init__(self) -> None:
        weights = (
            self.demand_weight,
            self.engagement_weight,
            self.velocity_weight,
            self.evidence_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("genome score weights must be non-negative")
        if not math.isclose(sum(weights), 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("genome score weights must sum to 1.0")


def slugify(value: str) -> str:
    """Create a stable, human-readable niche identifier."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_taxonomy_node(
    *, node_id: str, name: str, kind: NodeKind, parent_id: str | None = None,
    description: str = "", keywords: Sequence[str] = (), confidence: float = 0.0,
) -> NicheNode:
    """Create a candidate taxonomy node without claiming empirical validation."""
    return NicheNode(
        node_id=node_id,
        slug=slugify(name),
        name=name,
        kind=kind,
        parent_id=parent_id,
        description=description,
        keywords=tuple(dict.fromkeys(keyword.strip().lower() for keyword in keywords if keyword.strip())),
        confidence=confidence,
    )


def normalize_observations(observations: Iterable[NicheObservation]) -> list[NicheObservation]:
    """Return deterministic observation order for reproducible aggregation."""
    return sorted(observations, key=lambda item: (item.node_id, item.platform, item.observed_at, item.observation_id))


def score_niche(
    node_id: str,
    observations: Sequence[NicheObservation],
    *,
    demand_score: float,
    config: GenomeConfig | None = None,
) -> NicheScore:
    """Aggregate observations into an auditable opportunity score.

    Demand is supplied by an upstream research provider because no single
    platform exposes a universal demand metric. Engagement, velocity and
    evidence are normalized from the observed sample; the function never
    fabricates missing data.
    """
    cfg = config or GenomeConfig()
    if not 0.0 <= demand_score <= 1.0:
        raise ValueError("demand_score must be in [0, 1]")
    selected = [item for item in observations if item.node_id == node_id]
    if not selected:
        return NicheScore(
            node_id=node_id,
            demand_score=demand_score,
            engagement_score=0.0,
            velocity_score=0.0,
            evidence_score=0.0,
            opportunity_score=cfg.demand_weight * demand_score,
            sample_size=0,
        )

    engagement = min(1.0, sum(item.engagement_rate for item in selected) / len(selected))
    velocity = min(1.0, sum(item.viral_velocity for item in selected) / len(selected))
    evidence = min(1.0, sum(item.evidence_confidence for item in selected) / len(selected))
    opportunity = (
        cfg.demand_weight * demand_score
        + cfg.engagement_weight * engagement
        + cfg.velocity_weight * velocity
        + cfg.evidence_weight * evidence
    )
    return NicheScore(
        node_id=node_id,
        demand_score=demand_score,
        engagement_score=engagement,
        velocity_score=velocity,
        evidence_score=evidence,
        opportunity_score=opportunity,
        sample_size=len(selected),
    )


def infer_intersection_edges(
    nodes: Sequence[NicheNode], *, minimum_shared_keywords: int = 1,
) -> tuple[NicheEdge, ...]:
    """Create candidate cross-niche edges from explicit keyword overlap.

    This is a deterministic discovery heuristic, not a claim of causal
    relationship. Stronger edges should be promoted only after observations
    or external evidence confirm the intersection.
    """
    edges: list[NicheEdge] = []
    for index, left in enumerate(nodes):
        left_keywords = set(left.keywords)
        if not left_keywords:
            continue
        for right in nodes[index + 1 :]:
            if left.parent_id != right.parent_id and left.kind == right.kind == "gene":
                shared = left_keywords.intersection(right.keywords)
                if len(shared) >= minimum_shared_keywords:
                    edge_id = f"intersection:{left.node_id}:{right.node_id}"
                    strength = min(1.0, len(shared) / max(len(left_keywords | set(right.keywords)), 1))
                    edges.append(
                        NicheEdge(
                            edge_id=edge_id,
                            source_node_id=left.node_id,
                            target_node_id=right.node_id,
                            kind="intersects",
                            weight=strength,
                            evidence_count=0,
                            confidence=0.0,
                        )
                    )
    return tuple(edges)
