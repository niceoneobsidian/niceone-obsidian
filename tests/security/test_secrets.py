from datetime import timedelta

import pytest

from ois.security.secrets.core import ApiKeyManager, SecretRedactor, hash_api_key
from ois.security.secrets.scanner import SecretScanner


def test_key_is_hashed_and_scoped() -> None:
    manager = ApiKeyManager(pepper="test-only-pepper")
    record, raw = manager.create(
        owner_id="u",
        project_id="p",
        service_id="s",
        environment="development",
        name="x",
        scopes={"read"},
        expires_in=timedelta(hours=1),
    )
    assert raw not in record.key_hash
    assert record.key_hash == hash_api_key(raw, "test-only-pepper")
    assert manager.validate(raw, "read").id == record.id


def test_revocation_blocks_validation() -> None:
    manager = ApiKeyManager()
    record, raw = manager.create(
        owner_id="u",
        project_id="p",
        service_id="s",
        environment="test",
        name="x",
        scopes={"read"},
    )
    manager.revoke(record.id, "admin")
    with pytest.raises(PermissionError):
        manager.validate(raw)


def test_redaction() -> None:
    redacted = SecretRedactor(["secret"]).redact("token=secret")
    assert "secret" not in redacted


def test_scanner() -> None:
    findings = SecretScanner().scan_text("odk_prod_" + "A" * 40, "x.py")
    assert findings
