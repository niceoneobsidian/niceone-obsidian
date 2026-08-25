"""Supervision boundary; policy remains authoritative."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupervisionDecision:
    action: str
    reason: str


class Supervisor:
    def decide(self, *, status: str) -> SupervisionDecision:
        if status == "success":
            return SupervisionDecision("complete", "execution succeeded")
        return SupervisionDecision("recover", "execution requires recovery")
