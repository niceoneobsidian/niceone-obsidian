# OIS environment promotion

Production promotion is protected by GitHub Environment approval. Repository code cannot configure reviewers or secret values; those controls belong in GitHub repository settings.

Required setup:
- staging: protected environment and staging secret-manager references.
- production: required reviewers, deployment branch restrictions, production secrets.
- production secret provider: Vault or cloud workload identity, never env-only.

The deployment workflow validates the environment contract before reaching the deployment boundary. Provider-specific deployment commands remain deployment adapters.
