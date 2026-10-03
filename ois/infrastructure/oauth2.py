"""Provider-neutral OAuth 2.0 authorization-code framework."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OAuth2Config:
    provider: str
    authorization_url: str
    token_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = ()
    authorization_params: tuple[tuple[str, str], ...] = ()
    client_id_param: str = "client_id"
    client_secret_param: str = "client_secret"
    scope_separator: str = " "
    token_auth_method: str = "client_secret_post"


@dataclass(frozen=True)
class OAuth2Token:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: tuple[str, ...] = ()
    obtained_at: datetime | None = None
    raw: dict[str, object] | None = None

    @property
    def expires_at(self) -> datetime | None:
        if self.expires_in is None:
            return None
        return (self.obtained_at or datetime.now(UTC)) + timedelta(seconds=self.expires_in)

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "OAuth2Token":
        scope_value = payload.get("scope", "")
        scopes = tuple(str(scope_value).split()) if scope_value else ()
        return cls(
            access_token=str(payload["access_token"]),
            token_type=str(payload.get("token_type", "Bearer")),
            expires_in=int(str(payload["expires_in"])) if payload.get("expires_in") is not None else None,
            refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
            scope=scopes,
            obtained_at=datetime.now(UTC),
            raw=dict(payload),
        )


class OAuth2StateStore(Protocol):
    def put(self, state: str, *, provider: str, tenant_id: str, workspace_id: str) -> None: ...
    def consume(self, state: str, *, provider: str, tenant_id: str, workspace_id: str) -> bool: ...


class InMemoryOAuth2StateStore:
    def __init__(self) -> None:
        self._states: dict[str, tuple[str, str, str]] = {}

    def put(self, state: str, *, provider: str, tenant_id: str, workspace_id: str) -> None:
        self._states[state] = (provider, tenant_id, workspace_id)

    def consume(self, state: str, *, provider: str, tenant_id: str, workspace_id: str) -> bool:
        value = self._states.pop(state, None)
        return value == (provider, tenant_id, workspace_id)


class OAuth2Provider:
    """Provider-neutral authorization-code and refresh boundary."""

    def __init__(
        self,
        config: OAuth2Config,
        *,
        state_store: OAuth2StateStore | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.config = config
        self._state_store = state_store or InMemoryOAuth2StateStore()
        self._timeout = timeout

    def authorization_url(
        self, *, tenant_id: str, workspace_id: str, state: str | None = None
    ) -> tuple[str, str]:
        state_value = state or secrets.token_urlsafe(32)
        self._state_store.put(
            state_value,
            provider=self.config.provider,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        params = {
            self.config.client_id_param: self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.config.scope_separator.join(self.config.scopes),
            "state": state_value,
        }
        params.update(dict(self.config.authorization_params))
        return f"{self.config.authorization_url}?{urlencode(params)}", state_value

    def validate_state(self, state: str, *, tenant_id: str, workspace_id: str) -> None:
        if not self._state_store.consume(
            state, provider=self.config.provider, tenant_id=tenant_id, workspace_id=workspace_id
        ):
            raise PermissionError("invalid or replayed OAuth2 state")

    def exchange_code(self, code: str) -> OAuth2Token:
        fields = {
            self.config.client_id_param: self.config.client_id,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.config.redirect_uri,
        }
        if self.config.token_auth_method == "client_secret_post":
            fields[self.config.client_secret_param] = self.config.client_secret
        return self._token_request(fields)

    def refresh(self, refresh_token: str) -> OAuth2Token:
        fields = {
            self.config.client_id_param: self.config.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if self.config.token_auth_method == "client_secret_post":
            fields[self.config.client_secret_param] = self.config.client_secret
        return self._token_request(fields)

    def _token_request(self, fields: dict[str, str]) -> OAuth2Token:
        request = Request(
            self.config.token_url,
            data=urlencode(fields).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        if self.config.token_auth_method == "client_secret_basic":
            import base64

            raw = f"{self.config.client_id}:{self.config.client_secret}".encode()
            request.add_header("Authorization", f"Basic {base64.b64encode(raw).decode()}")
        with urlopen(request, timeout=self._timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict) or "access_token" not in payload:
            raise ValueError(f"{self.config.provider} OAuth2 token response is invalid")
        return OAuth2Token.from_payload(payload)
