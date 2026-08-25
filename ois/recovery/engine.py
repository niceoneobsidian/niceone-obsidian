"""Explicit recovery decisions; no silent retries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str


class RecoveryPlane:
    def decide(self, *, failure: str, attempt: int, max_attempts: int) -> RecoveryDecision:
        if attempt < max_attempts:
            return RecoveryDecision("retry", failure)
        return RecoveryDecision("escalate", failure)
