from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ois.autonomy import (
    ApprovalDecision,
    ApprovalGate,
    AutonomousLoop,
    AutonomousOperations,
    EventEnvelope,
    FailureRecovery,
    InMemoryApprovalStore,
    PolicyOutcome,
    AutomationPolicy,
    PolicyRule,
    SourceWorkflow,
    WorkflowTrigger,
)
