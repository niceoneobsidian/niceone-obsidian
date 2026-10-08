"""Optional provider SDK factories. Imports are deferred until a provider is selected."""
from __future__ import annotations
import os
from typing import Any

def build_vault_client() -> Any:
    import hvac
    return hvac.Client(url=os.environ["VAULT_ADDR"], token=os.environ.get("VAULT_TOKEN"))

def build_aws_client() -> Any:
    import boto3
    return boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))

def build_azure_client() -> Any:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    return SecretClient(vault_url=os.environ["AZURE_KEY_VAULT_URL"], credential=DefaultAzureCredential())

def build_gcp_client() -> Any:
    from google.cloud import secretmanager
    return secretmanager.SecretManagerServiceClient()

def build_infisical_client() -> Any:
    from infisical_client import ClientSettings, InfisicalClient
    return InfisicalClient(ClientSettings(
        client_id=os.environ["INFISICAL_CLIENT_ID"],
        client_secret=os.environ["INFISICAL_CLIENT_SECRET"],
        site_url=os.getenv("INFISICAL_SITE_URL", "https://app.infisical.com"),
    ))
