"""Provider-neutral image generation boundary with optional fal.ai adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class ImageGenerationError(RuntimeError):
    """Raised when an image provider is unavailable or returns invalid output."""


@dataclass(frozen=True)
class ImageAsset:
    provider: str
    model: str
    url: str
    request_id: str | None = None


class ImageGenerator:
    """Capability boundary for image generation; never grants publishing authority."""

    def __init__(self, generate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]]) -> None:
        self._generate = generate

    def generate(self, prompt: str, **options: Any) -> ImageAsset:
        result = self._generate(prompt, options)
        url = str(result.get("url", ""))
        if not url:
            raise ImageGenerationError("Image provider returned no asset URL")
        return ImageAsset(
            provider=str(result.get("provider", "unknown")),
            model=str(result.get("model", "unknown")),
            url=url,
            request_id=str(result["request_id"]) if result.get("request_id") else None,
        )


def fal_generate(prompt: str, options: Mapping[str, Any]) -> Mapping[str, Any]:
    """Optional fal.ai implementation; dependency and credentials remain runtime concerns."""

    try:
        import fal_client
    except ImportError as exc:
        raise ImageGenerationError("Install the approved fal.ai client to enable image generation") from exc

    model = str(options.get("model", "fal-ai/flux-2"))
    arguments = {"prompt": prompt}
    for key in ("image_size", "num_images"):
        if key in options:
            arguments[key] = options[key]

    try:
        handler = fal_client.submit(model, arguments=arguments)
        result = handler.get()
    except Exception as exc:
        raise ImageGenerationError(f"fal.ai request failed: {exc}") from exc

    images = result.get("images", [])
    if not images or not images[0].get("url"):
        raise ImageGenerationError("fal.ai returned no image URL")
    return {
        "provider": "fal.ai",
        "model": model,
        "url": images[0]["url"],
        "request_id": getattr(handler, "request_id", None),
    }
