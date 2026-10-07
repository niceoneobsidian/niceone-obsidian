"""Provider conformance manifests and fail-closed validation.

Manifests describe what a provider is expected to prove. They never promote
runtime evidence by declaration alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

REQUIRED_SECTIONS = {
    "provider",
    "adapter",
    "registration",
    "capabilities",
    "tools",
    "auth",
    "credentials",
    "scopes",
    "policy",
    "reliability",
    "events",
    "evidence",
    "tests",
    "live",
}

@dataclass(frozen=True)
class ProviderConformanceManifest:
    provider: str
    adapter: str
    registration: str
    capabilities: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    auth_schemes: tuple[str, ...] = ()
    credential_types: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    policy_actions: tuple[str, ...] = ()
    rate_limit: str | None = None
    retry: str | None = None
    timeout_seconds: float | None = None
    idempotency: str | None = None
    events: tuple[str, ...] = ()
    required_tests: tuple[str, ...] = ()
    live_mode: str = "read_only"
    allow_writes: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProviderConformanceManifest":
        missing = REQUIRED_SECTIONS - set(data)
        if missing:
            raise ValueError(f"provider manifest missing sections: {sorted(missing)}")
        reliability = data["reliability"]
        auth = data["auth"]
        credentials = data["credentials"]
        tests = data["tests"]
        live = data["live"]
        return cls(
            provider=str(data["provider"]),
            adapter=str(data["adapter"]),
            registration=str(data["registration"]),
            capabilities=tuple(data["capabilities"]),
            tools=tuple(data["tools"]),
            auth_schemes=tuple(auth.get("schemes", ())),
            credential_types=tuple(credentials.get("types", ())),
            scopes=tuple(data["scopes"]),
            policy_actions=tuple(data["policy"].get("actions", ())),
            rate_limit=reliability.get("rate_limit"),
            retry=reliability.get("retry"),
            timeout_seconds=reliability.get("timeout_seconds"),
            idempotency=reliability.get("idempotency"),
            events=tuple(data["events"]),
            required_tests=tuple(tests.get("required", ())),
            live_mode=str(live.get("mode", "read_only")),
            allow_writes=bool(live.get("allow_writes", False)),
            metadata=dict(data.get("metadata", {})),
        )

    def validate_safe_live_policy(self) -> None:
        if self.live_mode != "read_only" or self.allow_writes:
            raise ValueError(
                "provider conformance live policy must be read_only with writes disabled"
            )

def load_manifest(data: Mapping[str, Any]) -> ProviderConformanceManifest:
    manifest = ProviderConformanceManifest.from_dict(data)
    manifest.validate_safe_live_policy()
    return manifest
