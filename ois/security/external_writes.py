"""Hard OIS external-write safety boundary."""

from __future__ import annotations

from dataclasses import dataclass


class ExternalWriteDenied(PermissionError):
    pass


@dataclass(frozen=True)
class WriteAuthorization:
    environment: str
    capability_id: str
    approved: bool
    evidence_verified: bool
    dry_run: bool = False


class ExternalWriteGate:
    def __init__(
        self,
        *,
        external_writes_enabled: bool,
        require_approval: bool = True,
        require_evidence: bool = True,
    ) -> None:
        self.external_writes_enabled = external_writes_enabled
        self.require_approval = require_approval
        self.require_evidence = require_evidence

    def authorize(self, decision: WriteAuthorization) -> None:
        if not self.external_writes_enabled:
            raise ExternalWriteDenied("external writes are disabled")
        if decision.dry_run:
            raise ExternalWriteDenied("dry-run execution cannot perform external writes")
        if self.require_approval and not decision.approved:
            raise ExternalWriteDenied("external write requires explicit approval")
        if self.require_evidence and not decision.evidence_verified:
            raise ExternalWriteDenied("external write requires verified capability evidence")
        if decision.environment not in {"staging", "production"}:
            raise ExternalWriteDenied(
                f"external writes are not permitted from environment: {decision.environment}"
            )
