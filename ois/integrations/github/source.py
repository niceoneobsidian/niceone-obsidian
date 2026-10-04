"""GitHub REST source routed through the governed SourceGateway."""
from __future__ import annotations

from ois.infrastructure.source_adapters.http import HttpSourceAdapter
from ois.infrastructure.source_gateway import AuthScheme


class GitHubSource(HttpSourceAdapter):
    source_id = "github.rest.user"

    def __init__(self, *, timeout: float = 20.0) -> None:
        super().__init__(
            source_id=self.source_id,
            url="https://api.github.com/user",
            timeout=timeout,
            connector_version="github-rest-v3",
            auth_scheme=AuthScheme.BEARER,
            headers={"Accept": "application/vnd.github+json"},
        )
