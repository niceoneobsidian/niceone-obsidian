"""Compatibility facade for the canonical OIS Kernel Supervisor."""

from ois.kernel.supervisor import (
    SupervisionAction,
    SupervisionRequest,
    Supervisor,
    SupervisionDecision,
    SupervisorError,
    AgentSelectionError,
)

__all__ = [
    "AgentSelectionError",
    "SupervisionAction",
    "SupervisionDecision",
    "SupervisionRequest",
    "Supervisor",
    "SupervisorError",
]
