from __future__ import annotations

from enum import Enum


class ExecutionStatus(str, Enum):
    RECEIVED = "received"
    NORMALIZED = "normalized"
    UNDERSTOOD = "understood"
    CLASSIFIED = "classified"
    RISK_ASSESSED = "risk_assessed"
    CONTEXT_RETRIEVED = "context_retrieved"
    ROUTED = "routed"
    PLANNED = "planned"
    PLAN_VALIDATED = "plan_validated"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    OBSERVING = "observing"
    VALIDATING = "validating"
    UPDATING_STATE = "updating_state"
    CHECKPOINTING = "checkpointing"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"
    REPLANNING = "replanning"
    ESCALATED = "escalated"
    STOPPED = "stopped"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FailureClass(str, Enum):
    TRANSIENT = "transient"
    PARAMETER = "parameter"
    TOOL = "tool"
    PLAN = "plan"
    STATE = "state"
    PERMISSION = "permission"
    SAFETY = "safety"
    UNKNOWN = "unknown"


class InvocationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class SideEffectLevel(str, Enum):
    NONE = "none"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"
