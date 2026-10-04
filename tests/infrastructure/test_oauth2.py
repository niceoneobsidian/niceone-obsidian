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


def _config(**overrides: object) -> OAuth2Config:
    values: dict[str, object] = {
        "provider": "test",
        "authorization_url": "https://example.test/auth",
        "token_url": "https://example.test/token",
        "client_id": "client",
        "client_secret": "secret",
        "redirect_uri": "https://app.test/callback",
        "scopes": ("a", "b"),
    }
    values.update(overrides)
    return OAuth2Config(**values)  # type: ignore[arg-type]


def test_oauth2_authorization_url_generates_state_and_scopes() -> None:
    provider = OAuth2Provider(_config())
    url, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["client"]
    assert query["scope"] == ["a b"]
    assert query["state"] == [state]
    provider.validate_state(state, tenant_id="t1", workspace_id="w1")


def test_oauth2_state_is_one_time_and_tenant_scoped() -> None:
    store = InMemoryOAuth2StateStore()
    provider = OAuth2Provider(_config(), state_store=store)
    _, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    with pytest.raises(PermissionError):
        provider.validate_state(state, tenant_id="t2", workspace_id="w1")
    provider.validate_state(state, tenant_id="t1", workspace_id="w1")
    with pytest.raises(PermissionError):
        provider.validate_state(state, tenant_id="t1", workspace_id="w1")


def test_oauth2_state_expires() -> None:
    provider = OAuth2Provider(_config(state_ttl_seconds=1))
    _, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    store = provider._state_store
    state_value = store._states[state]
    store._states[state] = type(state_value)(
        state_value.provider,
        state_value.tenant_id,
        state_value.workspace_id,
        state_value.expires_at.replace(year=2000),
    )
    with pytest.raises(PermissionError):
        provider.validate_state(state, tenant_id="t1", workspace_id="w1")


def test_oauth2_config_rejects_insecure_provider_configuration() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OAuth2Provider(_config(token_url="http://example.test/token"))
    with pytest.raises(ValueError, match="HTTPS"):
        OAuth2Provider(_config(redirect_uri="http://localhost.evil/callback"))
    with pytest.raises(ValueError, match="fragment"):
        OAuth2Provider(_config(redirect_uri="https://app.test/callback#fragment"))
    with pytest.raises(ValueError, match="client ID"):
        OAuth2Provider(_config(client_id=""))
    with pytest.raises(ValueError, match="scope"):
        OAuth2Provider(_config(scopes=()))


def test_oauth2_refresh_preserves_existing_refresh_token() -> None:
    provider = OAuth2Provider(_config(provider="google"))
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


def test_oauth2_basic_auth_does_not_send_client_secret_in_body() -> None:
    provider = OAuth2Provider(_config(token_auth_method="client_secret_basic"))
    response = type(
        "Response",
        (),
        {
            "read": lambda self: b'{"access_token":"access"}',
            "__enter__": lambda self: self,
            "__exit__": lambda self, *_: None,
        },
    )()
    with patch("ois.infrastructure.oauth2.urlopen", return_value=response) as opened:
        provider.exchange_code("code")
    request = opened.call_args.args[0]
    assert b"client_secret" not in request.data
    assert request.get_header("Authorization") is not None


def test_oauth2_provider_parses_provider_specific_response_scope_separator() -> None:
    token = OAuth2Token.from_payload(
        {"access_token": "access", "scope": "user.info.basic,video.list"},
        scope_separator=",",
    )
    assert token.scope == ("user.info.basic", "video.list")


def test_oauth2_token_errors_are_structured() -> None:
    provider = OAuth2Provider(_config(provider="google"))
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


def test_oauth2_token_does_not_retain_raw_secret_payload() -> None:
    token = OAuth2Token.from_payload(
        {"access_token": "access", "refresh_token": "refresh", "expires_in": 60}
    )
    assert not hasattr(token, "raw")
