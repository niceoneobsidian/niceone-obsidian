import pytest

from ois.integration.live_harness import LiveTestConfig
from ois.integration.proof_chain import require_proof

@pytest.mark.parametrize("env", [
    {"OIS_LIVE_ALLOW_WRITES": "true"},
    {"OIS_LIVE_MODE": "write"},
])
def test_live_write_paths_are_rejected(monkeypatch, env):
    for key in ("OIS_LIVE_ALLOW_WRITES", "OIS_LIVE_MODE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        LiveTestConfig.from_env()

def test_policy_bypass_is_rejected():
    with pytest.raises(PermissionError):
        require_proof(
            tool="provider.write",
            capability="provider.write",
            provider="example",
            policy_action="write",
            authorized=False,
        )
