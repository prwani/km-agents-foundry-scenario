from __future__ import annotations

import os
from typing import Protocol

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

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
