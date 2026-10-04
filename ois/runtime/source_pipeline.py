"""Source-to-intelligence orchestration with policy and recovery boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ois.control_plane.source_policies import SourcePolicyStore
from ois.domains.social_intelligence.events import CanonicalSourceEvent
from ois.runtime.source_recovery import DeadLetterStore, SourceRecovery


@dataclass(frozen=True)
class PipelineResult:
    event_id: str
    accepted: bool
    dead_lettered: bool = False
    reason: str | None = None


class SourceIntelligencePipeline:
    """Authorize, deliver, and recover canonical source events."""

    def __init__(
        self,
        *,
        policies: SourcePolicyStore,
        recovery: SourceRecovery,
        dead_letters: DeadLetterStore,
        handler: Callable[[CanonicalSourceEvent], object] | None = None,
    ) -> None:
        self._policies = policies
        self._recovery = recovery
        self._dead_letters = dead_letters
        self._handler = handler

    def process(
        self,
        event: CanonicalSourceEvent,
        handler: Callable[[CanonicalSourceEvent], object] | None = None,
        *,
        credential_verified: bool = False,
    ) -> PipelineResult:
        try:
            self._policies.authorize(
                event.tenant_id,
                event.workspace_id,
                event.source_id,
                event_type=event.event_type,
                credential_present=credential_verified,
            )
        except (KeyError, PermissionError) as exc:
            return PipelineResult(event.event_id, False, False, str(exc))

        processor = handler or self._handler
        if processor is None:
            return PipelineResult(event.event_id, False, False, "intelligence_handler_not_configured")
        accepted = self._recovery.run(event, processor)
        dead_lettered = any(
            item.event.event_id == event.event_id
            for item in self._dead_letters.list(event.tenant_id, event.workspace_id)
        )
        return PipelineResult(
            event.event_id,
            accepted,
            dead_lettered,
            None if accepted else "processing_failed",
        )
