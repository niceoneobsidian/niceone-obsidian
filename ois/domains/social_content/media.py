"""Controlled media staging for external providers that require HTTPS asset URLs."""

from __future__ import annotations

import hashlib
import http.server
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


class MediaHostingError(RuntimeError):
    """Raised when media hosting cannot be safely initialized."""


@dataclass
class LocalMediaHost:
    """Local asset server with an optional externally managed HTTPS base URL."""

    media_folder: str = "./shared_media"
    port: int = 8585
    public_base_url: str | None = None

    def __post_init__(self) -> None:
        self.root = Path(self.media_folder).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._httpd: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._httpd is not None:
            return

        root = self.root

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(root), **kwargs)

            def log_message(self, format: str, *args: object) -> None:
                return

        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        try:
            self._httpd = ReusableTCPServer(("127.0.0.1", self.port), Handler)
        except OSError as exc:
            raise MediaHostingError(f"Unable to bind local media server: {exc}") from exc
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None
        self._thread = None

    def stage(self, data: bytes, *, extension: str = ".bin") -> str:
        if not extension.startswith("."):
            extension = f".{extension}"
        digest = hashlib.sha256(data).hexdigest()[:20]
        filename = f"asset_{digest}{extension}"
        (self.root / filename).write_bytes(data)
        return filename

    def public_url(self, filename: str) -> str:
        if not self.public_base_url:
            raise MediaHostingError("No authorized public HTTPS media boundary is configured")
        candidate = (self.root / filename).resolve()
        if self.root not in candidate.parents:
            raise MediaHostingError("Media path escapes the configured asset directory")
        if not candidate.is_file():
            raise MediaHostingError("Requested media asset does not exist")
        if not self.public_base_url.startswith("https://"):
            raise MediaHostingError("Public media boundary must use HTTPS")
        return f"{self.public_base_url.rstrip('/')}/{quote(candidate.name)}"
