"""Platform connector contracts and safe adapter patterns.

Adapters return domain records only. Authorization, credentials, rate limits,
approvals, audit and actual execution are delegated to OIS kernel services.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from .schemas import PublishIntent, SocialEvent


class SocialConnector(ABC):
    platform: str

    @abstractmethod
    def capabilities(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def normalize_event(self, payload: Mapping[str, Any]) -> SocialEvent:
        raise NotImplementedError

    @abstractmethod
    def publish(self, intent: PublishIntent) -> dict[str, Any]:
        """Return an external-action proposal/result; kernel must authorize it."""
        raise NotImplementedError

    def validate_publish(self, intent: PublishIntent) -> list[str]:
        errors: list[str] = []
        if intent.platform != self.platform:
            errors.append("platform mismatch")
        if not intent.account_ref:
            errors.append("account_ref is required")
        if not intent.content:
            errors.append("content is required")
        return errors


class GenericSocialConnector(SocialConnector):
    """Reference adapter for platform-specific implementations."""

    def __init__(
        self,
        platform: str,
        publish_callable: Callable[[PublishIntent], Mapping[str, Any]] | None = None,
    ) -> None:
        self.platform = platform
        self._publish_callable = publish_callable

    def capabilities(self) -> set[str]:
        return {"read_events", "publish"} if self._publish_callable else {"read_events"}

    def normalize_event(self, payload: Mapping[str, Any]) -> SocialEvent:
        occurred_at = payload.get("occurred_at")
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        if occurred_at is None:
            occurred_at = datetime.now().astimezone()
        return SocialEvent(
            platform=self.platform,
            event_type=str(payload.get("event_type", "unknown")),
            occurred_at=occurred_at,
            external_id=str(payload.get("id")) if payload.get("id") is not None else None,
            author_id=str(payload.get("author_id"))
            if payload.get("author_id") is not None
            else None,
            text=payload.get("text"),
            language=payload.get("language"),
            metrics=dict(payload.get("metrics", {})),
            entities=list(payload.get("entities", [])),
            raw=dict(payload),
        )

    def publish(self, intent: PublishIntent) -> dict[str, Any]:
        errors = self.validate_publish(intent)
        if errors:
            raise ValueError("invalid publish intent: " + "; ".join(errors))
        if self._publish_callable is None:
            raise RuntimeError(f"no publisher configured for {self.platform}")
        return dict(self._publish_callable(intent))


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, SocialConnector] = {}

    def register(self, connector: SocialConnector) -> None:
        if connector.platform in self._connectors:
            raise ValueError(f"connector already registered: {connector.platform}")
        self._connectors[connector.platform] = connector

    def get(self, platform: str) -> SocialConnector:
        try:
            return self._connectors[platform]
        except KeyError as exc:
            raise KeyError(f"unknown social platform: {platform}") from exc

    def platforms(self) -> tuple[str, ...]:
        return tuple(sorted(self._connectors))
