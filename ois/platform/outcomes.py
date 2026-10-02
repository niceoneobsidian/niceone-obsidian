from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .contracts import Lineage, PlatformIdentity, utc_now


@dataclass(frozen=True)
class OutcomeEvent:
    outcome_id: str
    identity: PlatformIdentity
    outcome_type: str
    value: object
    lineage: Lineage
    verified: bool
    observed_at: object = field(default_factory=utc_now)


class OutcomeStore:
    def __init__(self) -> None:
        self._items: dict[str, OutcomeEvent] = {}

    def record(
        self,
        identity: PlatformIdentity,
        outcome_type: str,
        value: object,
        *,
        parent_ids: tuple[str, ...] = (),
        verified: bool = False,
    ) -> OutcomeEvent:
        event = OutcomeEvent(
            uuid4().__str__(),
            identity,
            outcome_type,
            value,
            Lineage(uuid4().__str__(), parent_ids),
            verified,
        )
        self._items[event.outcome_id] = event
        return event

    def get(self, outcome_id: str) -> OutcomeEvent:
        return self._items[outcome_id]

    def verified(self, tenant_id: str) -> tuple[OutcomeEvent, ...]:
        return tuple(
            item
            for item in self._items.values()
            if item.identity.tenant_id == tenant_id and item.verified
        )
