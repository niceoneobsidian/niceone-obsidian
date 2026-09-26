"""Project source outbox evidence into the G1 provenance graph."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from ois.infrastructure.source_gateway.evidence import RawEvidence
from ois.infrastructure.source_gateway.outbox import OutboxEvent

from .graph import (
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    canonical_hash,
    deterministic_entity_id,
)


class EvidenceReader(Protocol):
    def evidence(self, evidence_id: str) -> RawEvidence | None: ...


class EvidenceGraphProjector:
    """Materialize durable raw evidence referenced by outbox events."""

    def __init__(
        self, graph: EvidenceGraph, evidence_reader: EvidenceReader | None = None
    ) -> None:
        self._graph = graph
        self._evidence_reader = evidence_reader

    def project(self, event: OutboxEvent) -> tuple[str, ...]:
        if event.event_type != "source.raw_evidence.created":
            return ()

        raw = self._load_evidence(event)
        payload = raw.payload if raw is not None else event.payload.get("payload", {})
        source_id = raw.source_id if raw is not None else event.payload.get("source_id")
        observed_at = (
            raw.collected_at
            if raw is not None
            else _parse_time(event.payload.get("collected_at"))
        )
        payload_hash = (
            raw.payload_hash
            if raw is not None
            else event.payload.get("payload_hash") or canonical_hash(payload)
        )

        evidence = GraphNode(
            event.aggregate_id,
            "evidence",
            event.tenant_id,
            event.workspace_id,
            source_id,
            payload,
            payload_hash,
            observed_at,
        )
        self._graph.upsert_node(evidence)
        created = [evidence.node_id]

        for topic in _topics(payload):
            entity_id = deterministic_entity_id("topic", topic)
            entity_payload = {
                "entity_type": "topic",
                "canonical_name": topic,
                "attributes": {},
            }
            entity = GraphNode(
                entity_id,
                "entity",
                event.tenant_id,
                event.workspace_id,
                None,
                entity_payload,
                canonical_hash(entity_payload),
                datetime.now(UTC),
            )
            self._graph.upsert_node(entity)
            edge = GraphEdge(
                f"mentions:{evidence.node_id}:{entity_id}",
                event.tenant_id,
                event.workspace_id,
                evidence.node_id,
                entity_id,
                "mentions",
                0.75,
                (evidence.node_id,),
                datetime.now(UTC),
            )
            if self._graph.add_edge(edge):
                created.append(edge.edge_id)

        return tuple(created)

    def _load_evidence(self, event: OutboxEvent) -> RawEvidence | None:
        if self._evidence_reader is None:
            return None
        evidence = self._evidence_reader.evidence(event.aggregate_id)
        if evidence is None:
            raise KeyError(
                f"raw evidence not found for outbox event {event.event_id}: "
                f"{event.aggregate_id}"
            )
        if (evidence.tenant_id, evidence.workspace_id) != (
            event.tenant_id,
            event.workspace_id,
        ):
            raise PermissionError("evidence/outbox scope mismatch")
        return evidence


def _parse_time(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)


def _topics(payload: dict[str, Any]) -> tuple[str, ...]:
    topics: set[str] = set()
    for key in ("title", "video_description", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            topics.add(value.strip())
    value = payload.get("topics")
    if isinstance(value, list):
        topics.update(str(item).strip() for item in value if str(item).strip())
    videos = payload.get("videos")
    if isinstance(videos, list):
        for video in videos:
            if not isinstance(video, dict):
                continue
            for key in ("title", "video_description"):
                value = video.get(key)
                if isinstance(value, str) and value.strip():
                    topics.add(value.strip())
    return tuple(sorted(topics))
