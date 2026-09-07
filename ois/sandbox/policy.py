from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


class SandboxPolicyError(ValueError):
    """Raised when a sandbox request violates its declared boundary."""


@dataclass(frozen=True)
class SandboxPolicy:
    """Declarative restrictions for agent-generated code/tool execution.

    This is a policy boundary, not a claim that the Python process itself is a
    secure sandbox. A production executor must enforce these fields in an
    isolated runtime such as a separately provisioned container/VM.
    """

    allowed_modules: FrozenSet[str] = frozenset()
    allowed_hosts: FrozenSet[str] = frozenset()
    allowed_paths: FrozenSet[str] = frozenset()
    allowed_secret_refs: FrozenSet[str] = frozenset()
    max_cpu_seconds: int = 5
    max_memory_mb: int = 256
    network_enabled: bool = False
    filesystem_write_enabled: bool = False

    def validate_request(
        self,
        *,
        modules: set[str] | None = None,
        hosts: set[str] | None = None,
        paths: set[str] | None = None,
        secret_refs: set[str] | None = None,
    ) -> None:
        modules = modules or set()
        hosts = hosts or set()
        paths = paths or set()
        secret_refs = secret_refs or set()

        if not modules <= self.allowed_modules:
            raise SandboxPolicyError("module allowlist violation")
        if not self.network_enabled and hosts:
            raise SandboxPolicyError("network access is disabled")
        if not hosts <= self.allowed_hosts:
            raise SandboxPolicyError("network host allowlist violation")
        if not self.filesystem_write_enabled and paths:
            raise SandboxPolicyError("filesystem writes are disabled")
        if not paths <= self.allowed_paths:
            raise SandboxPolicyError("filesystem path allowlist violation")
        if not secret_refs <= self.allowed_secret_refs:
            raise SandboxPolicyError("secret reference allowlist violation")
        if self.max_cpu_seconds <= 0 or self.max_memory_mb <= 0:
            raise SandboxPolicyError("sandbox resource limits must be positive")
