"""Minimal Vault KV v2 secret-manager adapter.

The adapter is intentionally narrow: OIS asks for a secret, while Vault owns
storage, encryption, access control and audit. Workload identity should provide
the Vault token in deployment; it is never committed to source.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request

class VaultError(RuntimeError): pass

class VaultKV2Backend:
    def __init__(self, address: str, token: str, *, timeout_s: float = 5.0) -> None:
        if not address.startswith("https://"):
            raise ValueError("Vault production address must use HTTPS")
        if not token: raise ValueError("Vault token is required")
        self.address=address.rstrip("/")
        self.token=token
        self.timeout_s=timeout_s

    def get(self, path: str, key: str) -> str | None:
        request=urllib.request.Request(
            f"{self.address}/v1/{path.lstrip('/')}",
            headers={"X-Vault-Token":self.token,"Accept":"application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request,timeout=self.timeout_s) as response:
                payload=json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError,urllib.error.URLError,OSError,json.JSONDecodeError) as exc:
            raise VaultError("Vault secret read failed") from exc
        data=payload.get("data",{}).get("data",{}) if isinstance(payload,dict) else {}
        value=data.get(key)
        return str(value) if value is not None else None
