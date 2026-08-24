"""System-of-systems composition contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitectureComponent:
    name: str
    version: str
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class SystemManifest:
    version: str
    components: tuple[ArchitectureComponent, ...]
