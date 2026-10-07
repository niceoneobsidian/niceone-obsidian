from __future__ import annotations

import pytest

from ois.config.settings import ConfigurationError, OISSettings, validate_startup
from ois.governance.activation import ActivationEvidence, ActivationState, CapabilityActivationGate
from ois.infrastructure.http_client import CircuitBreaker, CircuitOpenError, HttpClient
from ois.integration.integration_registry import (
    IntegrationError,
    IntegrationRegistry,
    IntegrationSpec,
)
from ois.security.external_writes import ExternalWriteDenied, ExternalWriteGate, WriteAuthorization


def test_production_rejects_debug():
    with pytest.raises(ConfigurationError):
        OISSettings.from_env({"OIS_ENVIRONMENT": "production", "OIS_DEBUG": "true"}).validate()


def test_production_requires_external_secret_provider():
    with pytest.raises(ConfigurationError):
        validate_startup({"OIS_ENVIRONMENT": "production", "OIS_SECRET_PROVIDER": "env"})


def test_test_environment_cannot_enable_external_writes():
    with pytest.raises(ConfigurationError):
        OISSettings.from_env(
            {
                "OIS_ENVIRONMENT": "test",
                "OIS_EXTERNAL_APIS_ENABLED": "true",
                "OIS_EXTERNAL_WRITES_ENABLED": "true",
            }
        ).validate()


def test_external_write_gate_is_deny_by_default():
    with pytest.raises(ExternalWriteDenied):
        ExternalWriteGate(external_writes_enabled=False).authorize(
            WriteAuthorization("production", "social.publish", True, True)
        )


def test_activation_gate_requires_production_verification():
    gate = CapabilityActivationGate(ActivationEvidence(True, True, True, True, False, True, True))
    assert gate.can_activate(ActivationState.CANARY)
    assert not gate.can_activate(ActivationState.PRODUCTION)


def test_integration_registry_requires_credentials_for_writes():
    with pytest.raises(IntegrationError):
        IntegrationRegistry().register(
            IntegrationSpec("meta", "meta", "https://graph.facebook.com", supports_write=True)
        )


def test_circuit_breaker_opens():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_s=60)
    breaker.failure()
    breaker.failure()
    with pytest.raises(CircuitOpenError):
        breaker.before_request()


def test_http_retry_policy_is_conservative():
    assert HttpClient(max_retries=3, retry_enabled=True).max_retries == 3
