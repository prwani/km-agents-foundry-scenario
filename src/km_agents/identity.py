from __future__ import annotations

import os
from typing import Protocol

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, OnBehalfOfCredential

from .config import ConfigurationError


class TokenCredential(Protocol):
    def get_token(self, *scopes: str, **kwargs: object) -> object: ...


def azure_credential() -> TokenCredential:
    environment = os.getenv("KM_AGENTS_ENVIRONMENT", "production").lower()
    if environment == "development":
        return DefaultAzureCredential()
    if environment != "production":
        raise ConfigurationError(
            "KM_AGENTS_ENVIRONMENT must be either development or production"
        )
    return ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))


def foundry_obo_credential(user_assertion: str) -> TokenCredential:
    tenant_id = os.getenv("ENTRA_TENANT_ID")
    client_id = os.getenv("ENTRA_PORTAL_CLIENT_ID")
    client_secret = os.getenv("ENTRA_CLIENT_SECRET")
    if not user_assertion or not tenant_id or not client_id or not client_secret:
        raise ConfigurationError(
            "A user assertion plus ENTRA_TENANT_ID, ENTRA_PORTAL_CLIENT_ID, and "
            "ENTRA_CLIENT_SECRET are required for Foundry OBO"
        )
    return OnBehalfOfCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        user_assertion=user_assertion,
    )
