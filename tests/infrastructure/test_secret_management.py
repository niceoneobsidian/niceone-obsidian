from datetime import UTC, datetime, timedelta

import pytest

from ois.infrastructure.secrets import (
    CredentialHealthManager,
    CredentialLifecycleManager,
    CredentialStatus,
    EnvironmentSecretProvider,
    HealthStatus,
    SecretManager,
    SecretMetadata,
    SecretState,
)


def _manager():
    provider = EnvironmentSecretProvider({"TEST_TOKEN": "initial"})
    manager = SecretManager(
        provider,
        {
            "TEST_TOKEN": SecretMetadata(
                "TEST_TOKEN", "test", "test", required=True, rotation_days=1
            )
        },
    )
    return manager


def test_secret_manager_fail_closed_for_missing_required_secret():
    manager = SecretManager(
        EnvironmentSecretProvider(),
        {"MISSING": SecretMetadata("MISSING", "test", "test", required=True)},
    )
    assert manager.validate("MISSING") is False
    with pytest.raises(KeyError):
        manager.require("MISSING")


def test_secret_manager_blocks_revoked_secret():
    manager = _manager()
    manager.update_metadata(
        SecretMetadata("TEST_TOKEN", "test", "test", required=True, state=SecretState.REVOKED)
    )
    with pytest.raises(PermissionError):
        manager.get("TEST_TOKEN")


def test_rotation_and_expiry():
    manager = _manager()
    lifecycle = CredentialLifecycleManager(manager)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lifecycle.register(manager.metadata("TEST_TOKEN"), now=now)
    lifecycle.rotate("TEST_TOKEN", value="replacement", now=now)
    health = CredentialHealthManager(manager, lifecycle)
    assert health.check("TEST_TOKEN", now=now).status is HealthStatus.HEALTHY
    assert lifecycle.status("TEST_TOKEN", now=now + timedelta(days=2)) is CredentialStatus.EXPIRING


def test_revoke_and_health():
    manager = _manager()
    lifecycle = CredentialLifecycleManager(manager)
    lifecycle.register(manager.metadata("TEST_TOKEN"))
    lifecycle.revoke("TEST_TOKEN")
    health_status = CredentialHealthManager(manager, lifecycle).check("TEST_TOKEN")
    assert health_status
    assert health_status.status is HealthStatus.REVOKED
