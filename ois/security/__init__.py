"""OIS security primitives."""

from production.connectors import InMemorySecretProvider, SecretProvider

__all__ = ["InMemorySecretProvider", "SecretProvider"]
