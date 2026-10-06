"""Fail-closed live integration safety harness.

No credential is loaded unless explicitly enabled by the live-test environment.
Writes remain prohibited by default.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class LiveTestConfig:
    enabled: bool
    provider: str | None
    mode: str
    allow_writes: bool
    tenant_id: str
    workspace_id: str
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "LiveTestConfig":
        enabled = os.getenv("OIS_LIVE_TESTS", "").lower() in {"1", "true", "yes"}
        allow_writes = os.getenv("OIS_LIVE_ALLOW_WRITES", "").lower() in {"1", "true", "yes"}
        mode = os.getenv("OIS_LIVE_MODE", "read_only")
        cfg = cls(
            enabled=enabled,
            provider=os.getenv("OIS_LIVE_PROVIDER"),
            mode=mode,
            allow_writes=allow_writes,
            tenant_id=os.getenv("OIS_LIVE_TENANT", "live-test"),
            workspace_id=os.getenv("OIS_LIVE_WORKSPACE", "live-test"),
            timeout_seconds=float(os.getenv("OIS_LIVE_TIMEOUT", "20")),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.mode != "read_only":
            raise ValueError("live harness only permits read_only mode")
        if self.allow_writes:
            raise ValueError("live harness refuses write-enabled execution")
        if self.enabled and not self.provider:
            raise ValueError("OIS_LIVE_PROVIDER is required when live tests are enabled")
        if self.timeout_seconds <= 0:
            raise ValueError("OIS_LIVE_TIMEOUT must be positive")

def live_tests_enabled() -> bool:
    return LiveTestConfig.from_env().enabled
