from __future__ import annotations

from urllib.parse import urlsplit


def validate_http_url(value: str, *, label: str = "URL") -> None:
    message = f"{label} must be an absolute HTTP(S) URL without embedded credentials"
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError as exc:
        raise ValueError(message) from exc
    if not valid:
        raise ValueError(message)
