"""Stable, versioned contracts crossing OIS architectural boundaries."""

CONTRACT_VERSION = "1.0"

from .execution import AuthorizationDecision, ExecutionRequest, ExecutionResult
from .evidence import EvidenceRecord

__all__ = ["CONTRACT_VERSION", "AuthorizationDecision", "ExecutionRequest", "ExecutionResult", "EvidenceRecord"]
