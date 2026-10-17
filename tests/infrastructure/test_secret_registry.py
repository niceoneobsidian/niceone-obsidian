from pathlib import Path

from ois.infrastructure.secrets.registry import load_registry


def test_canonical_secret_registry_loads():
    registry = load_registry(
        Path("config/secrets/registry.toml")
    )
    assert "github.token" in registry
    assert registry["github.token"].provider == "github"
    assert "github.rest.user" in registry["github.token"].scopes
