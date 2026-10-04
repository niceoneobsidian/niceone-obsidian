"""GitHub OAuth App provider configuration."""
from __future__ import annotations

from ois.infrastructure.oauth2 import OAuth2Config, OAuth2Provider


def build_github_oauth(
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    state_store=None,
) -> OAuth2Provider:
    return OAuth2Provider(
        OAuth2Config(
            provider="github",
            authorization_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=("read:user", "user:email"),
            authorization_params=(("allow_signup", "true"),),
        ),
        state_store=state_store,
    )
