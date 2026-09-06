"""Tenant-scoped semantic knowledge contracts with provenance and versioning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class KnowledgeAssertion:
    assertion_id: str
    tenant_id: str
    subject: str
    predicate: str
    object: str
    source_id: str
    confidence: float
    version: int
    observed_at: str
    learned: bool = False


class KnowledgeStore:
    """Minimal append-only knowledge substrate; learned facts never replace ground state."""

    def __init__(self) -> None:
        self._items: dict[str, list[KnowledgeAssertion]] = {}

    def append(self, assertion: KnowledgeAssertion) -> KnowledgeAssertion:
        if not assertion.tenant_id or not assertion.source_id:
            raise ValueError("knowledge requires tenant and provenance")
        if not 0.0 <= assertion.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        items = self._items.setdefault(assertion.tenant_id, [])
        if any(item.assertion_id == assertion.assertion_id for item in items):
            raise ValueError(f"duplicate assertion: {assertion.assertion_id}")
        items.append(assertion)
        return assertion

    def query(self, tenant_id: str, subject: str) -> tuple[KnowledgeAssertion, ...]:
        return tuple(item for item in self._items.get(tenant_id, ()) if item.subject == subject)

    def ground(self, tenant_id: str, subject: str) -> tuple[KnowledgeAssertion, ...]:
        return tuple(item for item in self.query(tenant_id, subject) if not item.learned)

    def learned(self, tenant_id: str, subject: str) -> tuple[KnowledgeAssertion, ...]:
        return tuple(item for item in self.query(tenant_id, subject) if item.learned)


def new_assertion(
    assertion_id: str,
    tenant_id: str,
    subject: str,
    predicate: str,
    object: str,
    source_id: str,
    *,
    confidence: float = 1.0,
    version: int = 1,
    learned: bool = False,
) -> KnowledgeAssertion:
    return KnowledgeAssertion(
        assertion_id=assertion_id,
        tenant_id=tenant_id,
        subject=subject,
        predicate=predicate,
        object=object,
        source_id=source_id,
        confidence=confidence,
        version=version,
        observed_at=datetime.now(UTC).isoformat(),
        learned=learned,
    )
