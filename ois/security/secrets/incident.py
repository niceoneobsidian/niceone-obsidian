"""Automated credential incident containment and recovery hooks."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
import secrets

@dataclass(frozen=True)
class Incident:
    incident_id: str
    kind: str
    resource_id: str
    severity: str
    created_at: str

class IncidentResponseAutomation:
    def __init__(self, revoke: Callable[[str], None], invalidate: Callable[[str], None] | None = None, audit: Any = None) -> None:
        self.revoke, self.invalidate, self.audit = revoke, invalidate, audit
    def contain(self, incident: Incident) -> None:
        self.revoke(incident.resource_id)
        if self.invalidate: self.invalidate(incident.resource_id)
        if self.audit: self.audit.record("security.incident.contained", incident.incident_id, incident.resource_id, {"kind": incident.kind, "severity": incident.severity})
    def handle_anomaly(self, resource_id: str, kind: str, severity: str = "high") -> Incident:
        incident = Incident(secrets.token_hex(12), kind, resource_id, severity, datetime.now(UTC).isoformat())
        self.contain(incident)
        return incident
