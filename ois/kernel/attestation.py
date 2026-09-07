from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass


class AttestationConfigurationError(RuntimeError):
    """Raised when the signing secret is not configured safely."""


@dataclass(frozen=True)
class AttestationPayload:
    """Canonical fields covered by an OIS admission attestation."""

    tenant_id: str
    execution_id: str
    gate_id: str
    decision: str
    side_effect_hash: str
    workflow_version: str

    def canonical_bytes(self) -> bytes:
        value = {
            "decision": self.decision,
            "execution_id": self.execution_id,
            "gate_id": self.gate_id,
            "schema_version": 1,
            "side_effect_hash": self.side_effect_hash,
            "tenant_id": self.tenant_id,
            "workflow_version": self.workflow_version,
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


class EvidenceLedgerSigner:
    """HMAC-SHA256 signer with key material supplied by the deployment secret store."""

    @staticmethod
    def _key() -> bytes:
        raw = os.environ.get("OIS_ATTESTATION_SECRET")
        if not raw:
            raise AttestationConfigurationError(
                "OIS_ATTESTATION_SECRET must be supplied by the runtime secret store"
            )
        key = raw.encode("utf-8")
        if len(key) < 32:
            raise AttestationConfigurationError(
                "OIS_ATTESTATION_SECRET must contain at least 32 bytes"
            )
        return key

    @classmethod
    def sign(cls, payload: AttestationPayload) -> str:
        return hmac.new(cls._key(), payload.canonical_bytes(), hashlib.sha256).hexdigest()

    @classmethod
    def verify(cls, payload: AttestationPayload, signature: str) -> bool:
        if not signature:
            return False
        expected = cls.sign(payload)
        return hmac.compare_digest(expected, signature)
