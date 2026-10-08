from ois.security.conformance import run_conformance

def test_security_conformance() -> None:
    results = run_conformance()
    assert all(results.values()), results
