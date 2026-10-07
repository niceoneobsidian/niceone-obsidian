import pytest

from ois.integration.live_harness import LiveTestConfig


@pytest.mark.live
def test_live_provider_read_only() -> None:
    cfg = LiveTestConfig.from_env()
    if not cfg.enabled:
        pytest.skip("live integration tests are disabled")
    assert cfg.mode == "read_only"
    assert cfg.allow_writes is False
    assert cfg.provider
    # Provider-specific authentication/read/evidence assertions belong here once
    # credentials are provisioned through the protected CI environment.
