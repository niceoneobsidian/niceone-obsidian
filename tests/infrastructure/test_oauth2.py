from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from ois.infrastructure.oauth2 import (
    InMemoryOAuth2StateStore,
    OAuth2Config,
    OAuth2Error,
    OAuth2Provider,
    OAuth2Token,
)


def test_oauth2_authorization_url_generates_state_and_scopes() -> None:
    provider = OAuth2Provider(
        OAuth2Config(
            provider="test",
            authorization_url="https://example.test/auth",
            token_url="https://example.test/token",
            client_id="client",
            client_secret="secret",
            redirect_uri="https://app.test/callback",
            scopes=("a", "b"),
        )
    )
    url, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["client"]
    assert query["scope"] == ["a b"]
    assert query["state"] == [state]
    provider.validate_state(state, tenant_id="t1", workspace_id="w1")


def test_oauth2_state_is_one_time_and_tenant_scoped() -> None:
    store = InMemoryOAuth2StateStore()
    provider = OAuth2Provider(
        OAuth2Config(
            provider="test",
            authorization_url="https://example.test/auth",
            token_url="https://example.test/token",
            client_id="client",
            client_secret="secret",
            redirect_uri="https://app.test/callback",
        ),
        state_store=store,
    )
    _, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    provider.validate_state(state, tenant_id="t1", workspace_id="w1")
    with pytest.raises(PermissionError):
        provider.validate_state(state, tenant_id="t1", workspace_id="w1")


def test_oauth2_refresh_preserves_existing_refresh_token() -> None:
    provider = OAuth2Provider(
        OAuth2Config(
            provider="google",
            authorization_url="https://example.test/auth",
            token_url="https://example.test/token",
            client_id="client",
            client_secret="secret",
            redirect_uri="https://app.test/callback",
        )
    )
    response = type(
        "Response",
        (),
        {
            "read": lambda self: b'{"access_token":"new-access","expires_in":3600}',
            "__enter__": lambda self: self,
            "__exit__": lambda self, *_: None,
        },
    )()
    with patch("ois.infrastructure.oauth2.urlopen", return_value=response):
        token = provider.refresh("old-refresh")
    assert token.access_token == "new-access"
    assert token.refresh_token == "old-refresh"


def test_oauth2_token_errors_are_structured() -> None:
    provider = OAuth2Provider(
        OAuth2Config(
            provider="google",
            authorization_url="https://example.test/auth",
            token_url="https://example.test/token",
            client_id="client",
            client_secret="secret",
            redirect_uri="https://app.test/callback",
        )
    )
    error = HTTPError(
        "https://example.test/token",
        400,
        "Bad Request",
        {},
        BytesIO(b'{"error":"invalid_grant","error_description":"code expired"}'),
    )
    with (
        patch("ois.infrastructure.oauth2.urlopen", side_effect=error),
        pytest.raises(OAuth2Error) as raised,
    ):
        provider.exchange_code("expired")
    assert raised.value.provider == "google"
    assert raised.value.operation == "authorization_code"
    assert raised.value.error_code == "invalid_grant"
    assert raised.value.category == "provider_rejected"
    assert raised.value.retryable is False
    assert raised.value.as_dict()["message"] == "code expired"


def test_oauth2_token_from_payload_can_preserve_refresh_token() -> None:
    token = OAuth2Token.from_payload(
        {"access_token": "access"},
        refresh_token="refresh",
    )
    assert token.refresh_token == "refresh"
