"""Provider-neutral OAuth 2.0 authorization-code framework."""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.error import HTTPError, URLError
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


class OAuth2Error(RuntimeError):
    """Structured token-endpoint failure with retry and provider context."""

    def __init__(
        self,
        *,
        provider: str,
        operation: str,
        category: str,
        message: str,
        error_code: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.category = category
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "category": self.category,
            "error_code": self.error_code,
            "status_code": self.status_code,
            "retryable": self.retryable,
            "message": str(self),
        }


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
    def from_payload(
        cls,
        payload: dict[str, object],
        *,
        refresh_token: str | None = None,
    ) -> OAuth2Token:
        scope_value = payload.get("scope", "")
        scopes = tuple(str(scope_value).split()) if scope_value else ()
        returned_refresh = payload.get("refresh_token")
        preserved_refresh = str(returned_refresh) if returned_refresh else refresh_token
        expires_in = (
            int(str(payload["expires_in"])) if payload.get("expires_in") is not None else None
        )
        return cls(
            access_token=str(payload["access_token"]),
            token_type=str(payload.get("token_type", "Bearer")),
            expires_in=expires_in,
            refresh_token=preserved_refresh,
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
        value = self._states.get(state)
        if value != (provider, tenant_id, workspace_id):
            return False
        del self._states[state]
        return True


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
        return self._token_request(fields, operation="authorization_code")

    def refresh(self, refresh_token: str) -> OAuth2Token:
        fields = {
            self.config.client_id_param: self.config.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if self.config.token_auth_method == "client_secret_post":
            fields[self.config.client_secret_param] = self.config.client_secret
        return self._token_request(
            fields,
            operation="refresh_token",
            refresh_token=refresh_token,
        )

    def _token_request(
        self,
        fields: dict[str, str],
        *,
        operation: str,
        refresh_token: str | None = None,
    ) -> OAuth2Token:
        request = Request(
            self.config.token_url,
            data=urlencode(fields).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        if self.config.token_auth_method == "client_secret_basic":
            raw = f"{self.config.client_id}:{self.config.client_secret}".encode()
            request.add_header("Authorization", f"Basic {base64.b64encode(raw).decode()}")

        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            payload = self._error_payload(exc)
            error_code = self._error_code(payload)
            description = self._error_description(payload) or str(exc.reason)
            category = (
                "provider_rejected"
                if exc.code < 500 and exc.code != 429
                else "provider_unavailable"
            )
            raise OAuth2Error(
                provider=self.config.provider,
                operation=operation,
                category=category,
                message=description,
                error_code=error_code,
                status_code=exc.code,
                retryable=exc.code >= 500 or exc.code == 429,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OAuth2Error(
                provider=self.config.provider,
                operation=operation,
                category="transport",
                message=str(exc),
                retryable=True,
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise OAuth2Error(
                provider=self.config.provider,
                operation=operation,
                category="invalid_response",
                message="OAuth2 token endpoint returned an invalid JSON response",
                retryable=True,
            ) from exc

        if not isinstance(payload, dict) or "access_token" not in payload:
            raise OAuth2Error(
                provider=self.config.provider,
                operation=operation,
                category="invalid_response",
                message=f"{self.config.provider} OAuth2 token response is invalid",
                retryable=True,
            )
        return OAuth2Token.from_payload(payload, refresh_token=refresh_token)

    @staticmethod
    def _error_payload(exc: HTTPError) -> dict[str, object]:
        try:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _error_code(payload: dict[str, object]) -> str | None:
        value = payload.get("error")
        return str(value) if value else None

    @staticmethod
    def _error_description(payload: dict[str, object]) -> str | None:
        for key in ("error_description", "message", "error"):
            value = payload.get(key)
            if value:
                return str(value)
        return None
