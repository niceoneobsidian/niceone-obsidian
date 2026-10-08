from datetime import timedelta
import pytest
from ois.security.secrets.core import ApiKeyManager,hash_api_key,SecretRedactor
from ois.security.secrets.scanner import SecretScanner

def test_key_is_hashed_and_scoped():
    m=ApiKeyManager(pepper="test-only-pepper")
    record,raw=m.create(owner_id="u",project_id="p",service_id="s",environment="development",name="x",scopes={"read"},expires_in=timedelta(hours=1))
    assert raw not in record.key_hash and record.key_hash==hash_api_key(raw, "test-only-pepper")
    assert m.validate(raw,"read").id==record.id

def test_revocation_blocks_validation():
    m=ApiKeyManager()
    record,raw=m.create(owner_id="u",project_id="p",service_id="s",environment="test",name="x",scopes={"read"})
    m.revoke(record.id,"admin")
    with pytest.raises(PermissionError): m.validate(raw)

def test_redaction():
    assert "secret" not in SecretRedactor(["secret"]).redact("token=secret")

def test_scanner():
    assert SecretScanner().scan_text("odk_prod_"+"A"*40,"x.py")
