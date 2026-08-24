"""Compliance evidence contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceRecord:
    control: str
    subject: str
    evidence_ref: str
    verified: bool
