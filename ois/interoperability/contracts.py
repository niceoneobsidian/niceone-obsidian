"""Interoperability contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterContract:
    protocol: str
    version: str
    endpoint: str
