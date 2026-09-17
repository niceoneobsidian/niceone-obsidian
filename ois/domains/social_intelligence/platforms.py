"""Platform and source adapter boundaries for Social Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .fabric import SocialEvent


@dataclass(frozen=True)
class PlatformSpec:
    platform_id: str
    display_name: str
    capabilities: tuple[str, ...]
    read_supported: bool = True
    write_supported: bool = False
    streaming_supported: bool = False
    requires_credentials: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


class PlatformAdapter(Protocol):
    spec: PlatformSpec

    def normalize(self, payload: Mapping[str, Any]) -> SocialEvent: ...

    def publish(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class CanonicalPlatformAdapter:
    """Reference adapter; real API implementations plug in without changing OIS contracts."""

    def __init__(self, spec: PlatformSpec) -> None:
        self.spec = spec

    def normalize(self, payload: Mapping[str, Any]) -> SocialEvent:
        return SocialEvent.from_payload(self.spec.platform_id, payload)

    def publish(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self.spec.write_supported:
            raise RuntimeError(f"Publishing is not enabled for {self.spec.platform_id}")
        raise NotImplementedError(
            f"No external publisher is configured for {self.spec.platform_id}; "
            "register an authorized adapter through the Tool Registry."
        )


class PlatformRegistry:
    """Version-neutral platform registry owned by the Social domain, execution owned by OIS."""

    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        platform_id = adapter.spec.platform_id
        if platform_id in self._adapters:
            raise ValueError(f"Duplicate platform adapter: {platform_id}")
        self._adapters[platform_id] = adapter

    def get(self, platform_id: str) -> PlatformAdapter:
        try:
            return self._adapters[platform_id]
        except KeyError as exc:
            raise KeyError(f"Unknown social platform: {platform_id}") from exc

    def list(self) -> tuple[PlatformSpec, ...]:
        return tuple(self._adapters[key].spec for key in sorted(self._adapters))

    def normalize(self, platform_id: str, payload: Mapping[str, Any]) -> SocialEvent:
        return self.get(platform_id).normalize(payload)


def default_platform_registry() -> PlatformRegistry:
    registry = PlatformRegistry()
    specs = (
        PlatformSpec("bluesky", "Bluesky", ("read", "publish", "stream"), write_supported=True, streaming_supported=True),
        PlatformSpec("mastodon", "Mastodon", ("read", "publish", "stream"), write_supported=True, streaming_supported=True),
        PlatformSpec("x", "X", ("read", "publish"), write_supported=True),
        PlatformSpec("instagram", "Instagram", ("read", "publish", "analytics"), write_supported=True),
        PlatformSpec("facebook", "Facebook", ("read", "publish", "analytics"), write_supported=True),
        PlatformSpec("tiktok", "TikTok", ("read", "publish", "analytics"), write_supported=True),
        PlatformSpec("youtube", "YouTube", ("read", "publish", "analytics"), write_supported=True),
        PlatformSpec("linkedin", "LinkedIn", ("read", "publish", "analytics"), write_supported=True),
        PlatformSpec("threads", "Threads", ("read", "publish"), write_supported=True),
        PlatformSpec("reddit", "Reddit", ("read", "publish"), write_supported=True),
        PlatformSpec("pinterest", "Pinterest", ("read", "publish", "analytics"), write_supported=True),
        PlatformSpec("github", "GitHub", ("read", "events")),
        PlatformSpec("web", "Web/News", ("read",)),
    )
    for spec in specs:
        registry.register(CanonicalPlatformAdapter(spec))
    return registry
