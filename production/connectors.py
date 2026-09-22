"""Governed external connector contract with retries, limits and secret isolation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Protocol
from urllib.parse import urlparse


class ConnectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConnectorRequest:
    operation: str
    url: str
    payload: Mapping[str, object] | None = None
    timeout_seconds: float = 10.0
    max_retries: int = 2


@dataclass(frozen=True)
class ConnectorResponse:
    status_code: int
    payload: object
    attempts: int
    duration_seconds: float


class SecretProvider(Protocol):
    def get(self, name: str) -> str: ...


class InMemorySecretProvider:
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def get(self, name: str) -> str:
        return self._values[name]


class EvidenceSink(Protocol):
    def append(self, execution_id: str, event_type: str, data: Mapping[str, object]) -> None: ...


class Connector(Protocol):
    def request(self, request: ConnectorRequest) -> ConnectorResponse: ...


class HTTPConnector:
    """Minimal HTTPS-only adapter boundary; concrete transports are injectable."""

    def __init__(
        self,
        transport: Callable[[str, Mapping[str, object] | None, float], tuple[int, object]],
        *,
        evidence: EvidenceSink | None = None,
    ) -> None:
        self.transport, self.evidence = transport, evidence

    def request(self, request: ConnectorRequest) -> ConnectorResponse:
        parsed = urlparse(request.url)
        if parsed.scheme != "https":
            raise ConnectorError("external connectors require HTTPS")
        start = monotonic()
        attempts = 0
        last_error: Exception | None = None
        for attempts in range(1, request.max_retries + 2):
            try:
                status, payload = self.transport(
                    request.url, request.payload, request.timeout_seconds
                )
                response = ConnectorResponse(status, payload, attempts, monotonic() - start)
                if self.evidence:
                    self.evidence.append(
                        "connector",
                        "connector.completed",
                        {"operation": request.operation, "status": status, "attempts": attempts},
                    )
                return response
            except Exception as exc:
                last_error = exc
                if attempts <= request.max_retries:
                    sleep(min(0.25 * attempts, 1.0))
        raise ConnectorError(
            f"connector failed after {attempts} attempts: {last_error}"
        ) from last_error
