"""Google OAuth 2.0 provider configuration."""
from __future__ import annotations
from ois.infrastructure.oauth2 import OAuth2Config, OAuth2Provider

def build_google_oauth(*, client_id: str, client_secret: str, redirect_uri: str, scopes: tuple[str, ...] = ("https://www.googleapis.com/auth/drive.metadata.readonly",), state_store=None) -> OAuth2Provider:
    return OAuth2Provider(
        OAuth2Config(
            provider="google",
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes,
            authorization_params=(("access_type", "offline"), ("include_granted_scopes", "true")),
        ),
        state_store=state_store,
    )
