from ois.integration.recovery_conformance import RECOVERY_CASES, RecoveryAction

def test_recovery_conformance_matrix_is_complete():
    assert len(RECOVERY_CASES) == 12
    assert {case.expected for case in RECOVERY_CASES} == {
        RecoveryAction.RETRY, RecoveryAction.FALLBACK, RecoveryAction.REPLAN,
        RecoveryAction.ESCALATE, RecoveryAction.TERMINATE,
    }
