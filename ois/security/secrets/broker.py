"""P2 provider-neutral secret broker and optional SDK adapters."""
from __future__ import annotations

import shutil
import subprocess
from typing import Any, Protocol

class SecretProvider(Protocol):
    name: str
    def get(self, metadata: Any, context: Any) -> str: ...
    def set(self, metadata: Any, value: str, context: Any) -> None: ...
    def delete(self, metadata: Any, context: Any) -> None: ...

class SecretBroker:
    def __init__(self, providers: dict[str, SecretProvider], policy: Any = None, audit: Any = None) -> None:
        self.providers = dict(providers)
        self.policy = policy
        self.audit = audit

    def _authorize(self, metadata: Any, context: Any) -> None:
        if self.policy:
            self.policy.authorize_secret(metadata, context)

    def get(self, metadata: Any, context: Any) -> str:
        self._authorize(metadata, context)
        provider = self.providers.get(metadata.provider)
        if provider is None:
            raise KeyError(f"provider not configured: {metadata.provider}")
        value = provider.get(metadata, context)
        if self.audit:
            self.audit.record("secret.read", context.actor_id, metadata.id)
        return value

    def set(self, metadata: Any, value: str, context: Any) -> None:
        self._authorize(metadata, context)
        self.providers[metadata.provider].set(metadata, value, context)
        if self.audit:
            self.audit.record("secret.write", context.actor_id, metadata.id)

    def delete(self, metadata: Any, context: Any) -> None:
        self._authorize(metadata, context)
        self.providers[metadata.provider].delete(metadata, context)
        if self.audit:
            self.audit.record("secret.delete", context.actor_id, metadata.id)

class LocalKeychainProvider:
    name = "local-keychain"

    def _run(self, *args: str, input_value: str | None = None) -> str:
        binary = "security" if shutil.which("security") else "secret-tool" if shutil.which("secret-tool") else None
        if binary is None:
            raise RuntimeError("no supported OS keychain CLI")
        process = subprocess.run((binary, *args), input=input_value, text=True, capture_output=True, check=False)
        if process.returncode:
            raise RuntimeError(process.stderr.strip() or "keychain operation failed")
        return process.stdout.strip()

    @staticmethod
    def _name(metadata: Any) -> str:
        return metadata.name if hasattr(metadata, "name") else str(metadata)

    def get(self, metadata: Any, context: Any = None) -> str:
        name = self._name(metadata)
        if shutil.which("security"):
            return self._run("find-generic-password", "-a", "ois", "-s", name, "-w")
        return self._run("lookup", "service", "ois", "attribute", name)

    def set(self, metadata: Any, value: str, context: Any = None) -> None:
        name = self._name(metadata)
        if shutil.which("security"):
            self._run("add-generic-password", "-U", "-a", "ois", "-s", name, "-w", value)
        else:
            self._run("store", "--label", f"OIS:{name}", "service", "ois", "attribute", name, input_value=value)

    def delete(self, metadata: Any, context: Any = None) -> None:
        name = self._name(metadata)
        if shutil.which("security"):
            self._run("delete-generic-password", "-a", "ois", "-s", name)
        else:
            self._run("clear", "service", "ois", "attribute", name)

class _OptionalClient:
    name = "provider"

    def __init__(self, client: Any = None) -> None:
        self.client = client

    def _need(self) -> Any:
        if self.client is None:
            raise RuntimeError(f"configure {self.name} SDK/client")
        return self.client

class InfisicalProvider(_OptionalClient):
    name = "infisical"
    def get(self, metadata, context): return str(self._need().get_secret(metadata.name))
    def set(self, metadata, value, context): self._need().set_secret(metadata.name, value)
    def delete(self, metadata, context): self._need().delete_secret(metadata.name)

class VaultProvider(_OptionalClient):
    name = "vault"
    def get(self, metadata, context): return str(self._need().secrets.kv.v2.read_secret_version(path=metadata.reference)["data"]["data"]["value"])
    def set(self, metadata, value, context): self._need().secrets.kv.v2.create_or_update_secret(path=metadata.reference, secret={"value": value})
    def delete(self, metadata, context): self._need().secrets.kv.v2.delete_metadata_and_all_versions(path=metadata.reference)

class AwsSecretsManagerProvider(_OptionalClient):
    name = "aws"
    def get(self, metadata, context): return str(self._need().get_secret_value(SecretId=metadata.reference)["SecretString"])
    def set(self, metadata, value, context): self._need().put_secret_value(SecretId=metadata.reference, SecretString=value)
    def delete(self, metadata, context): self._need().delete_secret(SecretId=metadata.reference, RecoveryWindowInDays=7)

class AzureKeyVaultProvider(_OptionalClient):
    name = "azure"
    def get(self, metadata, context): return str(self._need().get_secret(metadata.reference).value)
    def set(self, metadata, value, context): self._need().set_secret(metadata.reference, value)
    def delete(self, metadata, context): self._need().begin_delete_secret(metadata.reference)

class GcpSecretManagerProvider(_OptionalClient):
    name = "gcp"
    def get(self, metadata, context): return self._need().access_secret_version(name=metadata.reference).payload.data.decode()
    def set(self, metadata, value, context): self._need().add_secret_version(parent=metadata.reference, payload={"data": value.encode()})
    def delete(self, metadata, context): self._need().delete_secret(name=metadata.reference)
