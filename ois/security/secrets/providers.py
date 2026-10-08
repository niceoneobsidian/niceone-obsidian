"""Optional provider SDK factories. Imports are deferred until a provider is selected."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any

def build_vault_client() -> Any:
    import hvac
    return hvac.Client(url=os.environ["VAULT_ADDR"], token=os.environ.get("VAULT_TOKEN"))

def build_aws_client() -> Any:
    import boto3
    return boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))

def build_azure_client() -> Any:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    return SecretClient(vault_url=os.environ["AZURE_KEY_VAULT_URL"], credential=DefaultAzureCredential())

def build_gcp_client() -> Any:
    from google.cloud import secretmanager
    return secretmanager.SecretManagerServiceClient()

def build_infisical_client() -> Any:
    from infisical_client import ClientSettings, InfisicalClient
    return InfisicalClient(ClientSettings(
        client_id=os.environ["INFISICAL_CLIENT_ID"],
        client_secret=os.environ["INFISICAL_CLIENT_SECRET"],
        site_url=os.getenv("INFISICAL_SITE_URL", "https://app.infisical.com"),
    ))

@dataclass(frozen=True, slots=True)
class ProviderHealth:
    name: str
    available: bool
    healthy: bool
    capabilities: frozenset[str]
    detail: str = ""

class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, tuple[object, frozenset[str]]] = {}

    def register(self, name: str, provider: object, capabilities: frozenset[str] = frozenset()) -> None:
        self._providers[name] = (provider, capabilities)

    def discover(self, name: str) -> frozenset[str]:
        return self._providers[name][1]

    def health(self, name: str) -> ProviderHealth:
        if name not in self._providers:
            return ProviderHealth(name, False, False, frozenset(), "not configured")
        provider, capabilities = self._providers[name]
        try:
            checker = getattr(provider, "health", None)
            healthy = bool(checker()) if checker else True
            return ProviderHealth(name, True, healthy, capabilities)
        except Exception as exc:
            return ProviderHealth(name, True, False, capabilities, str(exc))

    def failover(self, preferred: list[str]) -> tuple[str, object]:
        for name in preferred:
            if name in self._providers and self.health(name).healthy:
                return name, self._providers[name][0]
        raise RuntimeError("no healthy secret provider available")
