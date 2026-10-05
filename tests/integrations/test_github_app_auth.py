from pathlib import Path

import pytest

from ois.integrations.github.app_auth import (
    GitHubAppAuthenticationError,
    GitHubAppAuthenticator,
    GitHubAppConfig,
    GitHubAppConfigurationError,
)


def test_config_reads_required_environment_values() -> None:
    config = GitHubAppConfig.from_env(
        {
            "GITHUB_APP_ID": "12345",
            "GITHUB_APP_INSTALLATION_ID": "67890",
            "GITHUB_APP_PRIVATE_KEY_PATH": "~/.config/ois/github-app/key.pem",
            "GITHUB_API_BASE_URL": "https://api.github.com",
        }
    )
    assert config.app_id == "12345"
    assert config.installation_id == "67890"
    assert config.private_key_path == Path("~/.config/ois/github-app/key.pem").expanduser()


def test_config_rejects_missing_values() -> None:
    with pytest.raises(GitHubAppConfigurationError):
        GitHubAppConfig.from_env({})


def test_config_rejects_non_numeric_ids() -> None:
    with pytest.raises(GitHubAppConfigurationError):
        GitHubAppConfig.from_env(
            {
                "GITHUB_APP_ID": "app",
                "GITHUB_APP_INSTALLATION_ID": "installation",
                "GITHUB_APP_PRIVATE_KEY_PATH": "/tmp/key.pem",
            }
        )


def test_access_token_is_cached_until_refresh_margin(monkeypatch, tmp_path) -> None:
    key_path = tmp_path / "key.pem"
    key_path.write_text("test-private-key", encoding="utf-8")
    config = GitHubAppConfig("123", "456", key_path)

    clock_value = 1_000.0
    calls = 0

    def clock() -> float:
        return clock_value

    def fake_encode(claims, key, algorithm):
        assert claims["iss"] == "123"
        assert key == "test-private-key"
        assert algorithm == "RS256"
        return "app-jwt"

    def fake_exchange(app_jwt):
        nonlocal calls
        calls += 1
        assert app_jwt == "app-jwt"
        return "installation-token", 2_000.0

    monkeypatch.setattr("ois.integrations.github.app_auth.jwt.encode", fake_encode)

    authenticator = GitHubAppAuthenticator(config, clock=clock, token_refresh_margin=60)
    monkeypatch.setattr(authenticator, "_exchange_for_installation_token", fake_exchange)

    assert authenticator.access_token() == "installation-token"
    assert authenticator.access_token() == "installation-token"
    assert calls == 1


def test_access_token_refreshes_inside_margin(monkeypatch, tmp_path) -> None:
    key_path = tmp_path / "key.pem"
    key_path.write_text("test-private-key", encoding="utf-8")
    config = GitHubAppConfig("123", "456", key_path)

    clock_value = 1_000.0

    def clock() -> float:
        return clock_value

    monkeypatch.setattr(
        "ois.integrations.github.app_auth.jwt.encode",
        lambda claims, key, algorithm: "app-jwt",
    )
    authenticator = GitHubAppAuthenticator(config, clock=clock, token_refresh_margin=60)
    responses = iter(
        (
            ("first-token", 1_050.0),
            ("second-token", 2_000.0),
        )
    )
    monkeypatch.setattr(
        authenticator,
        "_exchange_for_installation_token",
        lambda app_jwt: next(responses),
    )

    assert authenticator.access_token() == "first-token"
    assert authenticator.access_token() == "second-token"


def test_exchange_hides_github_error_body(monkeypatch, tmp_path) -> None:
    key_path = tmp_path / "key.pem"
    key_path.write_text("test-private-key", encoding="utf-8")
    config = GitHubAppConfig("123", "456", key_path)

    authenticator = GitHubAppAuthenticator(config)
    error = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
        "https://api.github.com/app/installations/456/access_tokens",
        401,
        "unauthorized",
        {},
        None,
    )
    monkeypatch.setattr(
        "ois.integrations.github.app_auth.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(error),
    )

    with pytest.raises(GitHubAppAuthenticationError, match="HTTP 401"):
        authenticator._exchange_for_installation_token("super-secret-jwt")
