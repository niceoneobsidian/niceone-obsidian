from urllib.parse import parse_qs, urlparse
from ois.infrastructure.oauth2 import InMemoryOAuth2StateStore, OAuth2Config, OAuth2Provider

def test_oauth2_authorization_url_generates_state_and_scopes() -> None:
    provider = OAuth2Provider(OAuth2Config(
        provider="test", authorization_url="https://example.test/auth",
        token_url="https://example.test/token", client_id="client",
        client_secret="secret", redirect_uri="https://app.test/callback",
        scopes=("a", "b"),
    ))
    url, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["client"]
    assert query["scope"] == ["a b"]
    assert query["state"] == [state]
    provider.validate_state(state, tenant_id="t1", workspace_id="w1")

def test_oauth2_state_is_one_time_and_tenant_scoped() -> None:
    store = InMemoryOAuth2StateStore()
    provider = OAuth2Provider(OAuth2Config(
        provider="test", authorization_url="https://example.test/auth",
        token_url="https://example.test/token", client_id="client",
        client_secret="secret", redirect_uri="https://app.test/callback",
    ), state_store=store)
    _, state = provider.authorization_url(tenant_id="t1", workspace_id="w1")
    provider.validate_state(state, tenant_id="t1", workspace_id="w1")
    try:
        provider.validate_state(state, tenant_id="t1", workspace_id="w1")
    except PermissionError:
        pass
    else:
        raise AssertionError("OAuth state must be one-time")
