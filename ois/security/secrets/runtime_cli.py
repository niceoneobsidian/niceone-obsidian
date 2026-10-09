"""CLI runtime bridge for governed secret injection."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
from .broker import (
    AwsSecretsManagerProvider, AzureKeyVaultProvider, GcpSecretManagerProvider,
    InfisicalProvider, LocalKeychainProvider, SecretBroker, VaultProvider,
)
from .providers import build_aws_client, build_azure_client, build_gcp_client, build_infisical_client, build_vault_client
from .registry import SecretRegistry
from .runtime import SecretRuntime

@dataclass(frozen=True)
class CliSecretContext:
    actor_id: str
    environment: str
    scopes: frozenset[str]

def build_runtime() -> tuple[SecretRuntime, SecretRegistry, CliSecretContext]:
    provider_name = os.getenv("OIS_SECRET_PROVIDER", "local-keychain")
    factories: dict[str, Any] = {
        "local-keychain": lambda: LocalKeychainProvider(),
        "vault": lambda: VaultProvider(build_vault_client()),
        "aws": lambda: AwsSecretsManagerProvider(build_aws_client()),
        "azure": lambda: AzureKeyVaultProvider(build_azure_client()),
        "gcp": lambda: GcpSecretManagerProvider(build_gcp_client()),
        "infisical": lambda: InfisicalProvider(build_infisical_client()),
    }
    if provider_name not in factories:
        raise RuntimeError(f"unsupported secret provider: {provider_name}")
    broker = SecretBroker({provider_name: factories[provider_name]()})
    return SecretRuntime(broker), SecretRegistry(), CliSecretContext(
        actor_id=os.getenv("OIS_ACTOR_ID", "cli"),
        environment=os.getenv("OIS_ENV", "development"),
        scopes=frozenset(filter(None, os.getenv("OIS_SECRET_SCOPES", "").split(","))),
    )

def run_command(secret_specs: list[str], command: list[str]) -> int:
    if not command:
        raise ValueError("command required")
    runtime, registry, context = build_runtime()
    records = {item.name: item for item in registry.list()}
    bindings: dict[str, tuple[object, object]] = {}
    for spec in secret_specs:
        if "=" not in spec:
            raise ValueError("secret binding must use SECRET_NAME=ENV_VAR")
        secret_name, env_name = spec.split("=", 1)
        if secret_name not in records:
            raise KeyError(f"secret metadata not found: {secret_name}")
        bindings[env_name] = (records[secret_name], context)
    return runtime.run(command, bindings)
