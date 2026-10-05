"""GitHub App installation authentication.

This module creates short-lived GitHub App installation access tokens from
an App ID, installation ID, and a PEM private key. Private key material and
issued access tokens are intentionally kept out of logs and domain records.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import jwt


class GitHubAppConfigurationError(ValueError):
    """Raised when required GitHub App configuration is missing or invalid."""


class GitHubAppAuthenticationError(RuntimeError):
    """Raised when GitHub rejects an App authentication request."""


@dataclass(frozen=True)
class GitHubAppConfig:
    app_id: str
    installation_id: str
    private_key_path: Path
    api_base_url: str = "https://api.github.com"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> GitHubAppConfig:
        values = os.environ if environ is None else environ
        app_id = values.get("GITHUB_APP_ID", "").strip()
        installation_id = values.get("GITHUB_APP_INSTALLATION_ID", "").strip()
        private_key_path = values.get("GITHUB_APP_PRIVATE_KEY_PATH", "").strip()
        api_base_url = values.get("GITHUB_API_BASE_URL", "https://api.github.com").strip()

        missing = [
            name
            for name, value in (
                ("GITHUB_APP_ID", app_id),
                ("GITHUB_APP_INSTALLATION_ID", installation_id),
                ("GITHUB_APP_PRIVATE_KEY_PATH", private_key_path),
            )
            if not value
        ]
        if missing:
            raise GitHubAppConfigurationError(
                "missing GitHub App configuration: " + ", ".join(missing)
            )
        if not app_id.isdigit() or not installation_id.isdigit():
            raise GitHubAppConfigurationError(
                "GITHUB_APP_ID and GITHUB_APP_INSTALLATION_ID must be numeric"
            )
        return cls(
            app_id=app_id,
            installation_id=installation_id,
            private_key_path=Path(private_key_path).expanduser(),
            api_base_url=api_base_url.rstrip("/"),
        )


class GitHubAppAuthenticator:
    """Mint and cache installation access tokens for one GitHub App installation."""

    def __init__(
        self,
        config: GitHubAppConfig,
        *,
        clock: Callable[[], float] = time.time,
        token_refresh_margin: int = 60,
        timeout: float = 20.0,
    ) -> None:
        self._config = config
        self._clock = clock
        self._token_refresh_margin = token_refresh_margin
        self._timeout = timeout
        self._cached_token: str | None = None
        self._cached_expires_at: float | None = None

    def access_token(self) -> str:
        if (
            self._cached_token
            and self._cached_expires_at
            and self._clock() < self._cached_expires_at - self._token_refresh_margin
        ):
            return self._cached_token

        private_key = self._read_private_key()
        now = int(self._clock())
        claims = {
            "iat": now - 60,
            "exp": now + 540,
            "iss": self._config.app_id,
        }
        app_jwt = jwt.encode(claims, private_key, algorithm="RS256")
        token, expires_at = self._exchange_for_installation_token(app_jwt)
        self._cached_token = token
        self._cached_expires_at = expires_at
        return token

    def invalidate(self) -> None:
        self._cached_token = None
        self._cached_expires_at = None

    def _read_private_key(self) -> str:
        try:
            return self._config.private_key_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GitHubAppConfigurationError(
                f"unable to read GitHub App private key: {self._config.private_key_path}"
            ) from exc

    def _exchange_for_installation_token(self, app_jwt: str) -> tuple[str, float]:
        url = (
            f"{self._config.api_base_url}/app/installations/"
            f"{self._config.installation_id}/access_tokens"
        )
        request = Request(
            url,
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "OIS-GitHub-App/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise GitHubAppAuthenticationError(
                f"GitHub App installation token request failed: HTTP {exc.code}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise GitHubAppAuthenticationError(
                "GitHub App installation token request failed"
            ) from exc

        token = payload.get("token")
        expires_at = payload.get("expires_at")
        if not isinstance(token, str) or not token:
            raise GitHubAppAuthenticationError("GitHub App response did not contain a token")
        if not isinstance(expires_at, str):
            raise GitHubAppAuthenticationError(
                "GitHub App response did not contain an expiration timestamp"
            )

        from datetime import datetime

        try:
            expires_epoch = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
        except ValueError as exc:
            raise GitHubAppAuthenticationError(
                "GitHub App response contained an invalid expiration timestamp"
            ) from exc
        return token, expires_epoch
