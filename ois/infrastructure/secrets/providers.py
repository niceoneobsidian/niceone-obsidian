"""Secret provider implementations.

Environment is intended for local/CI execution. Vault KV v2 is the concrete
production adapter; it uses stdlib HTTP and does not persist secrets in OIS.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class EnvironmentSecretProvider:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def get(self, name: str) -> str | None:
        return self._values.get(name) or os.getenv(name)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value

    def delete(self, name: str) -> None:
        self._values.pop(name, None)

    def exists(self, name: str) -> bool:
        return bool(self.get(name))


class VaultKV2SecretProvider:
    """HashiCorp Vault KV v2 adapter using a token supplied by the runtime."""

    def __init__(
        self,
        address: str,
        token: str,
        *,
        mount: str = "secret",
        namespace: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not address or not token:
            raise ValueError("Vault address and token are required")
        self.address = address.rstrip("/")
        self.token = token
        self.mount = mount.strip("/")
        self.namespace = namespace
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"X-Vault-Token": self.token, "Content-Type": "application/json"}
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace
        request = urllib.request.Request(
            f"{self.address}/v1/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Vault request failed with HTTP {exc.code}") from exc
        return json.loads(raw.decode("utf-8")) if raw else {}

    def get(self, name: str) -> str | None:
        payload = self._request("GET", f"{self.mount}/data/{name}")
        data = payload.get("data", {}).get("data", {})
        value = data.get("value")
        return str(value) if value is not None else None

    def set(self, name: str, value: str) -> None:
        self._request("POST", f"{self.mount}/data/{name}", {"data": {"value": value}})

    def delete(self, name: str) -> None:
        self._request("DELETE", f"{self.mount}/metadata/{name}")

    def exists(self, name: str) -> bool:
        try:
            return self.get(name) is not None
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise
