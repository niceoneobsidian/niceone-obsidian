"""Configuration architecture contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ConfigurationVersion:
    name: str
    version: str
    values: tuple[tuple[str, str], ...]
