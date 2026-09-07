from __future__ import annotations

import pytest

from ois.kernel.attestation import (
    AttestationConfigurationError,
    AttestationPayload,
    EvidenceLedgerSigner,
)
from ois.workflows.langgraph_runtime import LangGraphUnavailable, compile_interruptible_graph


def payload() -> AttestationPayload:
    return AttestationPayload(
        tenant_id="tenant-a",
        execution_id="execution-1",
        gate_id="gate-1",
        decision="APPROVED",
        side_effect_hash="abc123",
        workflow_version="1.0.0",
    )


def test_attestation_requires_deployment_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OIS_ATTESTATION_SECRET", raising=False)
    with pytest.raises(AttestationConfigurationError):
        EvidenceLedgerSigner.sign(payload())


def test_attestation_detects_context_or_decision_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIS_ATTESTATION_SECRET", "x" * 64)
    signature = EvidenceLedgerSigner.sign(payload())
    assert EvidenceLedgerSigner.verify(payload(), signature)
    assert not EvidenceLedgerSigner.verify(
        AttestationPayload(
            tenant_id="tenant-b",
            execution_id="execution-1",
            gate_id="gate-1",
            decision="APPROVED",
            side_effect_hash="abc123",
            workflow_version="1.0.0",
        ),
        signature,
    )
    assert not EvidenceLedgerSigner.verify(
        AttestationPayload(
            tenant_id="tenant-a",
            execution_id="execution-1",
            gate_id="gate-1",
            decision="REJECTED",
            side_effect_hash="abc123",
            workflow_version="1.0.0",
        ),
        signature,
    )


def test_short_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIS_ATTESTATION_SECRET", "too-short")
    with pytest.raises(AttestationConfigurationError):
        EvidenceLedgerSigner.sign(payload())


def test_langgraph_provider_is_explicit_optional_boundary() -> None:
    async def prepare(state):
        return state

    async def execute(state):
        return state

    async def validate(state):
        return state

    try:
        graph = compile_interruptible_graph(
            prepare=prepare,
            execute=execute,
            validate=validate,
        )
    except LangGraphUnavailable:
        # Core OIS tests must not require an optional provider package.
        return
    assert graph is not None
