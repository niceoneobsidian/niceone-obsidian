# Applied to the Vault role bound to the Kubernetes service account.
# Database credentials are issued dynamically by the database secrets engine.
path "database/creds/ois-tenant-pool" {
  capabilities = ["read"]
}

# Supervisor signing material is read-only. The worker cannot create, update,
# or destroy signing keys.
path "secret/data/ois/kernel/signing" {
  capabilities = ["read"]
}

# Explicitly deny KV metadata and destructive operations for the worker role.
path "secret/metadata/ois/kernel/signing" {
  capabilities = ["read"]
}
