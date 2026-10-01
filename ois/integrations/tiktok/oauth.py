"""TikTok Login Kit OAuth 2.0 server-side token exchange and refresh."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

"""TikTok Login Kit OAuth 2.0 server-side token exchange and refresh."""

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


@dataclass(frozen=True)
class TikTokTokenSet:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    open_id: str
    scopes: tuple[str, ...]
    token_type: str = "Bearer"

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> TikTokTokenSet:
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]),
            expires_in=int(str(payload["expires_in"])),
            refresh_expires_in=int(str(payload["refresh_expires_in"])),
            open_id=str(payload["open_id"]),
            scopes=tuple(str(payload.get("scope", "")).split(",")) if payload.get("scope") else (),
            token_type=str(payload.get("token_type", "Bearer")),
        )


@dataclass(frozen=True)
class TikTokClientCredentials:
    client_key: str
    client_secret: str


class TikTokOAuthClient:
    def __init__(self, credentials: TikTokClientCredentials, *, timeout: float = 15.0) -> None:
        self._credentials = credentials
        self._timeout = timeout

    def _post(self, fields: dict[str, str]) -> dict[str, object]:
        request = Request(
            TOKEN_URL,
            data=urlencode(fields).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache",
            },
            method="POST",
        )
        with urlopen(request, timeout=self._timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if "error" in payload:
            raise ValueError(
                f"TikTok OAuth error: {payload.get('error_description', payload['error'])}"
            )
        return cast(dict[str, Any], payload)

    def exchange_code(self, code: str, redirect_uri: str) -> TikTokTokenSet:
        return TikTokTokenSet.from_json(
            self._post(
                {
                    "client_key": self._credentials.client_key,
                    "client_secret": self._credentials.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                }
            )
        )

    def refresh(self, refresh_token: str) -> TikTokTokenSet:
        return TikTokTokenSet.from_json(
            self._post(
                {
                    "client_key": self._credentials.client_key,
                    "client_secret": self._credentials.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                }
            )
        )
