"""Secrets and key-management contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SecretRef:
    name: str
    version: str
