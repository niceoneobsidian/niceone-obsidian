"""Provider-specific rotation workflows with verify-before-activate semantics."""
from __future__ import annotations
import secrets
from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class RotationResult:
    provider: str
    secret_id: str
    old_version: str | None
    new_version: str | None
    state: str
    evidence: tuple[str, ...]

class RotationError(RuntimeError):
    pass

class RotationWorkflow:
    provider = "generic"
    def __init__(self, broker: Any, audit: Any = None) -> None:
        self.broker, self.audit = broker, audit
    def rotate(self, metadata: Any, context: Any, *, generate: Callable[[], str] | None = None, verify: Callable[[str], bool] | None = None) -> RotationResult:
        value = (generate or (lambda: secrets.token_urlsafe(48)))()
        old = self.broker.get(metadata, context)
        self.broker.set(metadata, value, context)
        if verify is not None and not verify(value):
            self.broker.set(metadata, old, context)
            if self.audit: self.audit.record("secret.rotation.rollback", context.actor_id, metadata.id)
            raise RotationError("rotated secret failed verification; previous value restored")
        if self.audit: self.audit.record("secret.rotation.completed", context.actor_id, metadata.id)
        return RotationResult(self.provider, metadata.id, None, None, "completed", ())

class InfisicalRotationWorkflow(RotationWorkflow):
    provider = "infisical"
class VaultRotationWorkflow(RotationWorkflow):
    provider = "vault"
class AzureRotationWorkflow(RotationWorkflow):
    provider = "azure"
class GcpRotationWorkflow(RotationWorkflow):
    provider = "gcp"

class AwsSecretsManagerRotationWorkflow(RotationWorkflow):
    provider = "aws"
    def rotate_versioned(self, client: Any, secret_id: str, context: Any, rotation_lambda_arn: str | None = None) -> RotationResult:
        kwargs = {"SecretId": secret_id, "RotateImmediately": True}
        if rotation_lambda_arn: kwargs["RotationLambdaARN"] = rotation_lambda_arn
        client.rotate_secret(**kwargs)
        if self.audit: self.audit.record("secret.rotation.requested", context.actor_id, secret_id)
        return RotationResult(self.provider, secret_id, None, None, "scheduled", ("aws.secretsmanager.rotate_secret",))
