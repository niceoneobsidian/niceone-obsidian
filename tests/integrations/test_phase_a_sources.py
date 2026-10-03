from ois.integrations.github import GitHubSource, build_github_oauth
from ois.integrations.google import GoogleDriveSource, build_google_oauth
from ois.integrations.meta import MetaFacebookSource, build_meta_oauth
from ois.integrations.tiktok import build_tiktok_oauth

def test_phase_a_provider_sources_use_governed_auth() -> None:
    assert GitHubSource().source_id == "github.rest.user"
    assert MetaFacebookSource().source_id == "meta.graph.me"
    assert GoogleDriveSource().source_id == "google.drive.files"
    assert build_tiktok_oauth(
        client_key="key", client_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "tiktok"
    assert build_github_oauth(
        client_id="id", client_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "github"
    assert build_meta_oauth(
        app_id="id", app_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "meta"
    assert build_google_oauth(
        client_id="id", client_secret="secret", redirect_uri="https://app.test/callback"
    ).config.provider == "google"
