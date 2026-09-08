from ois.sovereign.production import EvidenceLedger, E2ERunner, ExecutionRecord, RecoveryAction, RecoveryEngine, SecurityContext, SecurityGate


def test_evidence_chain_is_tamper_evident():
    ledger = EvidenceLedger()
    ledger.append("1", {"state": "running"})
    ledger.append("2", {"state": "succeeded"})
    assert ledger.verify()
    ledger._events[0]["event"]["state"] = "tampered"
    assert not ledger.verify()


def test_permission_denial_escalates_without_retry():
    gate = SecurityGate()
    allowed, _ = gate.authorize(SecurityContext("a", permissions=frozenset()), {"tool:write"}, "normal")
    assert not allowed
    assert RecoveryEngine().decide("permission_denied", 0).action == RecoveryAction.ESCALATE


def test_e2e_retry_then_success_and_idempotency():
    calls = {"n": 0}

    def execute(record: ExecutionRecord):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("temporary")
        return {"ok": True}

    runner = E2ERunner(execute)
    record = runner.run(ExecutionRecord("e1", "demo"), idempotency_key="k1")
    assert record.state == "succeeded"
    assert calls["n"] == 2
    again = runner.run(ExecutionRecord("e2", "demo"), idempotency_key="k1")
    assert again.output == {"ok": True}
    assert calls["n"] == 2
