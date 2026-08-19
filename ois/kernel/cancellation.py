from __future__ import annotations
from dataclasses import dataclass

from threading import RLock


class ExecutionCancellation(Exception):
    """Raised when an execution is cancelled."""


@dataclass
class CancellationToken:
    """
    Cooperative cancellation token.

    Cancellation is explicit and thread-safe. Runtime components can
    inspect this token at bounded execution boundaries and terminate
    safely without silently replaying or completing work.
    """

    def __init__(self) -> None:
        self._cancelled = False
        self._reason: str | None = None
        self._lock = RLock()

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled

    def cancel(self, reason: str | None = None) -> None:
        with self._lock:
            self._cancelled = True
            self._reason = reason

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ExecutionCancellation(
                self.reason or "Execution cancelled."
            )
