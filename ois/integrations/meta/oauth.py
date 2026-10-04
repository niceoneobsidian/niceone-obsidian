"""Meta OAuth configuration."""
from __future__ import annotations

from ois.infrastructure.oauth2 import OAuth2Config, OAuth2Provider


def build_meta_oauth(
    *,
    app_id: str,
    app_secret: str,
    redirect_uri: str,
    graph_version: str = "v24.0",
    state_store=None,
) -> OAuth2Provider:
    base = f"https://graph.facebook.com/{graph_version}"
    return OAuth2Provider(
        OAuth2Config(
            provider="meta",
            authorization_url=f"https://www.facebook.com/{graph_version}/dialog/oauth",
            token_url=f"{base}/oauth/access_token",
            client_id=app_id,
            client_secret=app_secret,
            redirect_uri=redirect_uri,
            scopes=("public_profile", "email"),
        ),
        state_store=state_store,
    )
