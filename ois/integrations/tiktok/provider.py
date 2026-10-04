"""TikTok Login Kit provider configuration."""
from __future__ import annotations

from ois.infrastructure.oauth2 import OAuth2Config, OAuth2Provider


def build_tiktok_oauth(
    *, client_key: str, client_secret: str, redirect_uri: str, state_store=None
) -> OAuth2Provider:
    return OAuth2Provider(
        OAuth2Config(
            provider="tiktok",
            authorization_url="https://www.tiktok.com/v2/auth/authorize/",
            token_url="https://open.tiktokapis.com/v2/oauth/token/",
            client_id=client_key,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=("user.info.basic", "video.list"),
            scope_separator=",",
            client_id_param="client_key",
            client_secret_param="client_secret",
            authorization_params=(("client_key", client_key),),
        ),
        state_store=state_store,
    )
