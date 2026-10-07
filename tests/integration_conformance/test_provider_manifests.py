from ois.integration.provider_manifest import load_manifest


def test_manifest_is_fail_closed_for_live_writes():
    manifest = load_manifest({
        "provider": "example",
        "adapter": "example.adapter",
        "registration": "SourceAdapterRegistry",
        "capabilities": ["read"],
        "tools": ["example.read"],
        "auth": {"schemes": ["oauth2"]},
        "credentials": {"types": ["oauth2"]},
        "scopes": ["read"],
        "policy": {"actions": ["read"]},
        "reliability": {
            "rate_limit": "provider",
            "retry": "bounded",
            "timeout_seconds": 20,
            "idempotency": "delivery-key",
        },
        "events": ["read"],
        "evidence": {"required": True},
        "tests": {"required": ["structural", "contract", "negative", "e2e"]},
        "live": {"mode": "read_only", "allow_writes": False},
    })
    assert manifest.live_mode == "read_only"
    assert manifest.allow_writes is False
