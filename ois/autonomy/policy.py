"""Policy-aware automation gates for autonomous workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ois.kernel.types import RiskLevel, SideEffectLevel


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    event_type: str | None = None
    maximum_risk: RiskLevel = RiskLevel.MEDIUM
    allow_side_effects: bool = False
    required_tags: tuple[str, ...] = ()

    def evaluate(self, context: Mapping[str, object]) -> tuple[bool, str]:
        if self.event_type is not None and context.get("event_type") != self.event_type:
            return False, "event type does not match"
        risk = RiskLevel(str(context.get("risk_level", RiskLevel.LOW.value)))
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        if order[risk] > order[self.maximum_risk] and not bool(
            context.get("requires_approval", False)
        ):
            return False, "risk exceeds automation policy"
        if (
            context.get("side_effects") not in (None, SideEffectLevel.NONE.value)
            and not self.allow_side_effects
        ):
            return False, "side effects are not permitted by automation policy"
        raw_tags = context.get("tags", ())
        tags = (
            {tag for tag in raw_tags if isinstance(tag, str)}
            if isinstance(raw_tags, tuple | list | set | frozenset)
            else set()
        )
        if not set(self.required_tags).issubset(tags):
            return False, "required policy tags are missing"
        return True, "rule matched"


@dataclass(frozen=True)
class PolicyEvaluation:
    outcome: PolicyOutcome
    rule_id: str | None
    reason: str
    requires_approval: bool = False


class AutomationPolicy:
    """First matching rule wins; no matching rule means deny."""

    def __init__(self, rules: tuple[PolicyRule, ...] = ()) -> None:
        self._rules = rules

    def evaluate(self, context: Mapping[str, object]) -> PolicyEvaluation:
        for rule in self._rules:
            matched, reason = rule.evaluate(context)
            if matched:
                requires_approval = bool(context.get("requires_approval", False))
                return PolicyEvaluation(
                    PolicyOutcome.APPROVAL_REQUIRED if requires_approval else PolicyOutcome.ALLOW,
                    rule.rule_id,
                    reason,
                    requires_approval=requires_approval,
                )
        return PolicyEvaluation(PolicyOutcome.DENY, None, "no automation policy rule matched")
