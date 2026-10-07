import pytest

from ois.integration.live_harness import LiveTestConfig
from ois.integration.proof_chain import require_proof

def test_proof_chain_requires_authorization():
    with pytest.raises(PermissionError):
        require_proof(
            tool="provider.read",
            capability="source.read",
            provider="provider",
            policy_action="read",
            authorized=False,
        )

def test_live_harness_is_read_only_by_default(monkeypatch):

    for key in (
        "OIS_LIVE_TESTS", "OIS_LIVE_PROVIDER", "OIS_LIVE_ALLOW_WRITES",
        "OIS_LIVE_MODE", "OIS_LIVE_TENANT", "OIS_LIVE_WORKSPACE", "OIS_LIVE_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)
    cfg = LiveTestConfig.from_env()
    assert cfg.enabled is False
    assert cfg.mode == "read_only"
    assert cfg.allow_writes is False


def test_live_harness_rejects_writes(monkeypatch):
    monkeypatch.setenv("OIS_LIVE_ALLOW_WRITES", "true")
    with pytest.raises(ValueError):
        LiveTestConfig.from_env()


def test_live_harness_requires_provider_when_enabled(monkeypatch):
    monkeypatch.setenv("OIS_LIVE_TESTS", "true")
    monkeypatch.delenv("OIS_LIVE_PROVIDER", raising=False)
    with pytest.raises(ValueError):
        LiveTestConfig.from_env()
