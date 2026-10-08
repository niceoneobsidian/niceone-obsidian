"""OIS secret management plane."""

from .manager import SecretManager, SecretMetadata, SecretState
from .providers import EnvironmentSecretProvider, VaultKV2SecretProvider
from .lifecycle import CredentialLifecycleManager, CredentialStatus
from .health import CredentialHealth, CredentialHealthManager, HealthStatus

__all__ = [
    "CredentialHealth",
    "CredentialHealthManager",
    "CredentialLifecycleManager",
    "CredentialStatus",
    "EnvironmentSecretProvider",
    "HealthStatus",
    "SecretManager",
    "SecretMetadata",
    "SecretState",
    "VaultKV2SecretProvider",
    "load_registry",
    "manager_from_registry",
]
