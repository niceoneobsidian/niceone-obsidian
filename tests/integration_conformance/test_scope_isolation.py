
class FakeCredentialResolver:
    def __init__(self):
        self.values = {("tenant-a", "workspace-a", "cred-a"): object()}
    def resolve(self, *, tenant_id, workspace_id, credential_id):
        if (tenant_id, workspace_id, credential_id) not in self.values:
            raise PermissionError("credential outside tenant/workspace scope")
        return self.values[(tenant_id, workspace_id, credential_id)]


def test_credential_scope_isolation():
    from ois.integration.credential_conformance import assert_credential_resolver_conformance
    proof = assert_credential_resolver_conformance(FakeCredentialResolver())
    assert proof.cross_tenant_blocked
