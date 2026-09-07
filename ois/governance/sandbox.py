"""Policy contract for isolated agent-generated code execution."""

from __future__ import annotations

from dataclasses import dataclass


class SandboxDenied(PermissionError):
    """Raised when a proposed sandbox execution violates policy."""


@dataclass(frozen=True)
class SandboxPolicy:
    cpu_seconds: int = 10
    memory_mb: int = 256
    timeout_seconds: int = 30
    max_output_bytes: int = 1_000_000
    network: bool = False
    filesystem_write: bool = False
    secrets: bool = False
    allowed_modules: frozenset[str] = frozenset()

    def validate(self) -> None:
        if self.cpu_seconds <= 0 or self.memory_mb <= 0 or self.timeout_seconds <= 0:
            raise ValueError("sandbox resource limits must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")


@dataclass(frozen=True)
class SandboxRequest:
    runtime: str
    code: str
    modules: frozenset[str] = frozenset()
    network: bool = False
    filesystem_write: bool = False
    secrets: bool = False
    timeout_seconds: int = 30


class SandboxAuthorizer:
    """Validate a code proposal against explicit resource and capability policy."""

    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        self.policy = policy or SandboxPolicy()
        self.policy.validate()

    def authorize(self, request: SandboxRequest) -> None:
        if request.runtime not in {"python", "node"}:
            raise SandboxDenied("unsupported sandbox runtime")
        if request.network and not self.policy.network:
            raise SandboxDenied("network access is denied")
        if request.filesystem_write and not self.policy.filesystem_write:
            raise SandboxDenied("filesystem writes are denied")
        if request.secrets and not self.policy.secrets:
            raise SandboxDenied("secret access is denied")
        if request.timeout_seconds > self.policy.timeout_seconds:
            raise SandboxDenied("requested timeout exceeds sandbox policy")
        unknown = request.modules - self.policy.allowed_modules
        if unknown:
            raise SandboxDenied(f"modules are not allowlisted: {sorted(unknown)}")
        if not request.code.strip():
            raise SandboxDenied("empty code is not executable")
