# Vault policy for Access Control Middleware
# This policy defines the permissions required for the middleware to access secrets
#
# To apply this policy in Vault:
# 1. vault policy write access-control-policy ./vault-policy.hcl
# 2. Assign to an AppRole or service account
#
# Policy allows:
# - Reading secrets for the middleware
# - Reading and listing metadata for audit purposes
# - NOT creating or deleting secrets (separation of concerns)

# Allow read access to access-control secrets
path "secret/data/access-control" {
  capabilities = ["read", "list"]
}

# Allow read access to access-control metadata (for audit timestamps)
path "secret/metadata/access-control" {
  capabilities = ["read", "list"]
}

# Allow reading secrets by key
path "secret/data/access-control/*" {
  capabilities = ["read"]
}

# Allow AppRole authentication
path "auth/approle/login" {
  capabilities = ["create", "read"]
}

# Allow token self-renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow reading token information
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

# Optional: Allow database credential generation (if using Vault DB plugin)
# Uncomment if database credentials are managed by Vault
# path "database/creds/access-control-reader" {
#   capabilities = ["read"]
# }
