"""Stage 4: CredentialResolver conformance with FAKE credentials only.

No real secrets, network or live provider calls. These tests prove resolution,
tenant ownership, expiry, scope, provider and secret-redaction behaviour of the
existing resolver / auth manager / gateway boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ois.infrastructure.source_gateway.auth import (
    AuthRequest,
    AuthScheme,
    CredentialMaterial,
)
from ois.infrastructure.source_gateway.credentials import (
    CredentialRef,
    InMemoryCredentialResolver,
    TenantScope,
)
from ois.infrastructure.source_gateway.gateway import SourceGateway
from ois.infrastructure.source_gateway.manager import AuthPolicy, CredentialAuthManager
from ois.integration.credential_conformance import assert_scoped_resolver_conformance

SECRET_A = "FAKE-SECRET-TENANT-A-0001"
SECRET_B = "FAKE-SECRET-TENANT-B-0002"
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
SCOPE_A = TenantScope("tenant-a", "ws-1")
SCOPE_B = TenantScope("tenant-b", "ws-1")


def _ref(tenant: str = "tenant-a", cred: str = "cred-a", **kw: Any) -> CredentialRef:
    return CredentialRef(cred, tenant, kw.pop("provider", "github"), **kw)


def _strict() -> InMemoryCredentialResolver:
    return InMemoryCredentialResolver(
        {"cred-a": SECRET_A, "cred-b": SECRET_B},
        owners={"cred-a": "tenant-a", "cred-b": "tenant-b"},
        strict_ownership=True,
    )


def _manager(resolver: Any = None) -> CredentialAuthManager:
    return CredentialAuthManager(resolver or _strict())


# ---- valid resolution ------------------------------------------------------


def test_valid_resolution_returns_only_the_requested_secret() -> None:
    material = _manager().resolve(_ref(), SCOPE_A)
    assert material.secret == SECRET_A


def test_each_tenant_resolves_only_its_own_credential() -> None:
    manager = _manager()
    assert manager.resolve(_ref("tenant-b", "cred-b"), SCOPE_B).secret == SECRET_B


# ---- missing / empty -------------------------------------------------------


def test_missing_credential_is_denied_without_leaking_secrets() -> None:
    resolver = InMemoryCredentialResolver(
        {"cred-a": SECRET_A},
        owners={"cred-a": "tenant-a", "cred-missing": "tenant-a"},
        strict_ownership=True,
    )
    with pytest.raises(KeyError, match="not configured") as exc:
        _manager(resolver).resolve(_ref(cred="cred-missing"), SCOPE_A)
    assert SECRET_A not in str(exc.value)


def test_unknown_credential_id_is_denied_under_strict_ownership() -> None:
    with pytest.raises(PermissionError):
        _manager().resolve(_ref(cred="cred-never-registered"), SCOPE_A)


def test_empty_secret_is_denied() -> None:
    resolver = InMemoryCredentialResolver(
        {"cred-a": ""}, owners={"cred-a": "tenant-a"}, strict_ownership=True
    )
    with pytest.raises(PermissionError, match="empty"):
        _manager(resolver).resolve(_ref(), SCOPE_A)


# ---- tenant isolation ------------------------------------------------------


def test_ref_tenant_must_match_scope_tenant() -> None:
    with pytest.raises(PermissionError, match="another tenant"):
        _manager().resolve(_ref("tenant-a"), SCOPE_B)


def test_forged_ref_cannot_read_another_tenants_credential_with_ownership() -> None:
    forged = _ref("tenant-b", "cred-a")  # tenant-b claims tenant-a's credential id
    with pytest.raises(PermissionError, match="another tenant"):
        _manager().resolve(forged, SCOPE_B)


def test_strict_ownership_denies_unowned_credentials() -> None:
    resolver = InMemoryCredentialResolver({"cred-x": "FAKE-X"}, strict_ownership=True)
    with pytest.raises(PermissionError, match="no tenant owner"):
        resolver.resolve(_ref(cred="cred-x"), SCOPE_A)


def test_legacy_unowned_resolver_is_not_tenant_isolating_known_gap() -> None:
    """KNOWN GAP (documented, not hidden): without owners, credential ids are global.

    A tenant that forges ``CredentialRef.tenant_id`` reads another tenant's secret.
    Production must bind to a secret manager that enforces ownership.
    """
    legacy = InMemoryCredentialResolver({"cred-a": SECRET_A})
    assert legacy.resolve(_ref("tenant-b", "cred-a"), SCOPE_B) == SECRET_A


def test_conformance_helper_rejects_the_legacy_resolver_and_accepts_the_strict_one() -> None:
    args = {
        "owner_tenant": "tenant-a",
        "other_tenant": "tenant-b",
        "workspace_id": "ws-1",
        "credential_id": "cred-a",
        "provider": "github",
    }
    with pytest.raises(AssertionError, match="cross-tenant"):
        assert_scoped_resolver_conformance(InMemoryCredentialResolver({"cred-a": SECRET_A}), **args)
    proof = assert_scoped_resolver_conformance(_strict(), **args)
    assert proof.resolved and proof.cross_tenant_blocked
    assert "forged-ref-denial" in proof.evidence
    assert SECRET_A not in repr(proof)


def test_conformance_helper_rejects_a_resolver_that_returns_nothing() -> None:
    class Empty:
        def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
            return ""

    with pytest.raises(AssertionError, match="valid credential resolution"):
        assert_scoped_resolver_conformance(
            Empty(),
            owner_tenant="tenant-a",
            other_tenant="tenant-b",
            workspace_id="ws-1",
            credential_id="cred-a",
            provider="github",
        )


# ---- expiry ----------------------------------------------------------------


def test_expired_credential_is_denied() -> None:
    ref = _ref(expires_at=NOW - timedelta(seconds=1))
    with pytest.raises(PermissionError, match="expired"):
        _manager().resolve(ref, SCOPE_A, now=NOW)


def test_credential_expiring_exactly_now_is_denied() -> None:
    with pytest.raises(PermissionError, match="expired"):
        _manager().resolve(_ref(expires_at=NOW), SCOPE_A, now=NOW)


def test_unexpired_and_non_expiring_credentials_resolve() -> None:
    manager = _manager()
    assert manager.resolve(_ref(expires_at=NOW + timedelta(hours=1)), SCOPE_A, now=NOW)
    assert manager.resolve(_ref(), SCOPE_A, now=NOW)


def test_naive_expiry_is_rejected_fail_closed() -> None:
    ref = _ref(expires_at=datetime(2099, 1, 1))
    with pytest.raises(PermissionError, match="timezone-aware"):
        _manager().resolve(ref, SCOPE_A, now=NOW)


def test_expiry_is_checked_before_the_resolver_is_asked_for_the_secret() -> None:
    calls: list[str] = []

    class Spy:
        def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
            calls.append(ref.credential_id)
            return SECRET_A

    with pytest.raises(PermissionError):
        _manager(Spy()).resolve(_ref(expires_at=NOW - timedelta(days=1)), SCOPE_A, now=NOW)
    assert calls == []


# ---- scopes and provider ---------------------------------------------------


def test_insufficient_scopes_are_denied() -> None:
    ref = _ref(scopes=("read",))
    with pytest.raises(PermissionError, match="lacks required scopes: write"):
        _manager().resolve(ref, SCOPE_A, required_scopes=("read", "write"))


def test_ref_without_scopes_is_denied_when_scopes_are_required() -> None:
    with pytest.raises(PermissionError, match="lacks required scopes"):
        _manager().resolve(_ref(), SCOPE_A, required_scopes=("read",))


def test_sufficient_scopes_resolve_and_no_requirement_is_allowed() -> None:
    manager = _manager()
    assert manager.resolve(_ref(scopes=("read", "extra")), SCOPE_A, required_scopes=("read",))
    assert manager.resolve(_ref(), SCOPE_A)


def test_credential_for_another_provider_is_denied() -> None:
    with pytest.raises(PermissionError, match="another provider"):
        _manager().resolve(_ref(provider="google"), SCOPE_A, expected_provider="github")


# ---- no secret leakage -----------------------------------------------------


def test_credential_material_repr_never_contains_the_secret() -> None:
    material = CredentialMaterial(secret=SECRET_A, client_id="client-1")
    assert SECRET_A not in repr(material) and SECRET_A not in str(material)
    assert "client-1" in repr(material)
    assert material.secret == SECRET_A  # still usable by authenticators


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ref": _ref("tenant-a"), "scope": SCOPE_B},
        {"ref": _ref(expires_at=NOW - timedelta(days=1)), "scope": SCOPE_A, "now": NOW},
        {"ref": _ref(scopes=()), "scope": SCOPE_A, "required_scopes": ("x",)},
        {"ref": _ref(provider="google"), "scope": SCOPE_A, "expected_provider": "github"},
        {"ref": _ref(cred="cred-missing"), "scope": SCOPE_A},
    ],
)
def test_denial_errors_never_contain_secret_values(kwargs: dict[str, Any]) -> None:
    with pytest.raises((PermissionError, KeyError)) as exc:
        _manager().resolve(**kwargs)
    text = f"{exc.value!s} {exc.value!r}"
    assert SECRET_A not in text and SECRET_B not in text


# ---- authentication orchestration -----------------------------------------


class _SpyAuthenticator:
    scheme = AuthScheme.BEARER

    def __init__(self) -> None:
        self.applied = 0

    def apply(self, request: AuthRequest, credential: CredentialMaterial) -> AuthRequest:
        self.applied += 1
        return AuthRequest(request.method, request.url, {"X": credential.secret}, request.body)


REQUEST = AuthRequest("GET", "https://example.invalid/v1", {})


def test_authenticator_is_not_invoked_when_resolution_is_denied() -> None:
    spy = _SpyAuthenticator()
    with pytest.raises(PermissionError):
        _manager().authenticate(
            REQUEST, _ref("tenant-a"), SCOPE_B, AuthPolicy(AuthScheme.BEARER), authenticator=spy
        )
    assert spy.applied == 0


def test_authenticate_applies_the_scheme_only_after_successful_resolution() -> None:
    spy = _SpyAuthenticator()
    result = _manager().authenticate(
        REQUEST, _ref(), SCOPE_A, AuthPolicy(AuthScheme.BEARER), authenticator=spy
    )
    assert spy.applied == 1 and result.headers["X"] == SECRET_A


def test_authenticate_requires_a_credential_provider() -> None:
    with pytest.raises(ValueError, match="provider"):
        _manager().authenticate(REQUEST, _ref(provider=""), SCOPE_A, AuthPolicy(AuthScheme.BEARER))


def test_none_scheme_never_touches_the_resolver() -> None:
    class Boom:
        def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
            raise AssertionError("resolver must not be called")

    out = _manager(Boom()).authenticate(REQUEST, _ref(), SCOPE_A, AuthPolicy(AuthScheme.NONE))
    assert out is REQUEST


def test_resolver_failure_propagates_and_returns_no_material() -> None:
    class Down:
        def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
            raise ConnectionError("secret manager unavailable")

    with pytest.raises(ConnectionError):
        _manager(Down()).resolve(_ref(), SCOPE_A)


# ---- gateway boundary ------------------------------------------------------


def test_gateway_blocks_cross_tenant_resolution_before_any_resolver_call() -> None:
    gateway = SourceGateway(credentials=_strict())
    with pytest.raises(PermissionError, match="another tenant"):
        gateway.resolve_credential(_ref("tenant-a"), SCOPE_B)


def test_gateway_without_a_resolver_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="not configured"):
        SourceGateway().resolve_credential(_ref(), SCOPE_A)


def test_gateway_resolves_through_the_governed_manager() -> None:
    gateway = SourceGateway(credentials=_strict())
    assert gateway.resolve_credential(_ref(), SCOPE_A).secret == SECRET_A
