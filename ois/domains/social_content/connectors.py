"""Platform connector contracts and safe adapter boundaries.

Concrete credentials and side effects remain outside the creative workflow. This
module records provider identity and requires an explicit publish authorization.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import ContentVariant, Platform


class PlatformConnector(Protocol):
    """Authorized platform side-effect boundary."""

    platform: Platform

    def publish(self, content: ContentVariant, *, authorized: bool) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ConnectorSpec:
    """Declarative metadata for a platform adapter."""

    platform: Platform
    provider: str
    mode: str
    status: str = "configured_not_verified"


CONNECTOR_SPECS: tuple[ConnectorSpec, ...] = (
    ConnectorSpec(Platform.TIKTOK, "TikTok Content Posting API", "official_api"),
    ConnectorSpec(Platform.INSTAGRAM, "Instagram Graph API", "official_api"),
    ConnectorSpec(Platform.X, "X API", "official_api"),
    ConnectorSpec(Platform.LINKEDIN, "LinkedIn API", "official_api"),
    ConnectorSpec(Platform.YOUTUBE, "YouTube API", "official_api"),
)


class AuthorizationRequiredError(PermissionError):
    """Raised when a connector is asked to cause an external side effect without approval."""


class SafeConnector:
    """Minimal connector base that prevents accidental live publishing."""

    def __init__(self, spec: ConnectorSpec) -> None:
        self.spec = spec
        self.platform = spec.platform

    def publish(self, content: ContentVariant, *, authorized: bool) -> Mapping[str, Any]:
        if not authorized:
            raise AuthorizationRequiredError(
                f"Publishing to {self.platform.value} requires explicit OIS authorization"
            )
        raise NotImplementedError(
            f"{self.spec.provider} adapter is declared but not runtime-verified"
        )
