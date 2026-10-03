"""Facebook/Meta Graph API source."""
from __future__ import annotations
from ois.infrastructure.source_adapters.http import HttpSourceAdapter
from ois.infrastructure.source_gateway import AuthScheme

class MetaFacebookSource(HttpSourceAdapter):
    source_id = "meta.graph.me"
    def __init__(self, *, graph_version: str = "v24.0", timeout: float = 20.0) -> None:
        super().__init__(
            source_id=self.source_id,
            url=f"https://graph.facebook.com/{graph_version}/me?fields=id,name,email",
            timeout=timeout,
            connector_version="meta-graph-v1",
            auth_scheme=AuthScheme.BEARER,
            headers={"Accept": "application/json"},
        )
