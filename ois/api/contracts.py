"""Platform API contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ApiVersion:
    major: int
    minor: int

@dataclass(frozen=True)
class ApiRoute:
    method: str
    path: str
    version: ApiVersion
