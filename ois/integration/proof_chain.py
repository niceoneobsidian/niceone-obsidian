"""Governed Tool -> Capability -> Policy -> Provider proof chain."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionProof:
    tool: str
    capability: str
    provider: str
    policy_action: str
    authorized: bool
    provider_reached: bool = False
    evidence: tuple[str, ...] = ()


def require_proof(
    *,
    tool: str,
    capability: str,
    provider: str,
    policy_action: str,
    authorized: bool,
) -> ExecutionProof:
    if not all((tool, capability, provider, policy_action)):
        raise ValueError("proof chain identifiers are required")
    if not authorized:
        raise PermissionError("policy denied provider execution")
    return ExecutionProof(
        tool=tool,
        capability=capability,
        provider=provider,
        policy_action=policy_action,
        authorized=True,
        evidence=("tool", "capability", "policy", "provider"),
    )
