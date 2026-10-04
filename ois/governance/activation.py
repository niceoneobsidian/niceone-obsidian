"""Evidence-gated capability activation state machine."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
class ActivationError(RuntimeError): pass
class ActivationState(StrEnum):
    OFF="OFF"; SHADOW="SHADOW"; CANARY="CANARY"; LIMITED="LIMITED"; PRODUCTION="PRODUCTION"; ROLLBACK="ROLLBACK"
@dataclass(frozen=True)
class ActivationEvidence:
    implementation_verified:bool
    tests_passed:bool
    integration_verified:bool
    deployment_verified:bool
    production_verified:bool=False
    policy_authorized:bool=False
    rollback_ready:bool=False
class CapabilityActivationGate:
    def __init__(self,evidence:ActivationEvidence)->None:self.evidence=evidence
    def can_activate(self,target:ActivationState)->bool:
        if target in {ActivationState.OFF,ActivationState.SHADOW}:return True
        base=(self.evidence.implementation_verified and self.evidence.tests_passed and self.evidence.integration_verified and self.evidence.deployment_verified and self.evidence.policy_authorized and self.evidence.rollback_ready)
        return base and (target not in {ActivationState.LIMITED,ActivationState.PRODUCTION} or self.evidence.production_verified)
    def require(self,target:ActivationState)->None:
        if not self.can_activate(target):raise ActivationError(f"activation gate failed for {target.value}")
