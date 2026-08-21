from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from uuid import uuid4
from typing import Any


@dataclass
class BrowserSession:
    session_id: str
    tenant_id: str
    engine: str
    metadata: dict[str, Any] = field(default_factory=dict)
    active: bool = True


class BrowserSessionManager:
    """Provider-neutral session lifecycle manager.

    Actual Playwright/Puppeteer/Browser-Use sessions are adapters implementing
    the same lifecycle. Secrets and proxy credentials must never be stored in
    this metadata object.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = RLock()

    def acquire(self, tenant_id: str, engine: str, metadata: dict[str, Any] | None = None) -> BrowserSession:
        session = BrowserSession(str(uuid4()), tenant_id, engine, metadata or {})
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def release(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.active = False

    def active_count(self, tenant_id: str | None = None) -> int:
        with self._lock:
            return sum(
                1 for s in self._sessions.values()
                if s.active and (tenant_id is None or s.tenant_id == tenant_id)
            )
