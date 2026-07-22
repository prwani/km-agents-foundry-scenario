from __future__ import annotations

from dataclasses import dataclass
import os

import jwt
from jwt import PyJWKClient


class AuthenticationError(ValueError):
    """Raised when the caller cannot be authenticated as the configured tenant user."""


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str
    tenant_id: str
    access_token: str


class EntraBearerTokenValidator:
    def __init__(self, tenant_id: str, audience: str) -> None:
        if not tenant_id or not audience:
            raise ValueError("Entra tenant ID and API audience are required")
        self._tenant_id = tenant_id
        self._audience = audience
        self._issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        self._keys = PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )

    @classmethod
    def from_environment(cls) -> "EntraBearerTokenValidator":
        tenant_id = os.getenv("ENTRA_TENANT_ID")
        audience = os.getenv("ENTRA_API_AUDIENCE")
        if not tenant_id or not audience:
            raise AuthenticationError(
                "ENTRA_TENANT_ID and ENTRA_API_AUDIENCE must be configured"
            )
        return cls(tenant_id=tenant_id, audience=audience)

    def authenticate(self, authorization: str | None) -> AuthenticatedUser:
        if not authorization:
            raise AuthenticationError("Bearer authentication is required")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            raise AuthenticationError("Authorization must use the Bearer scheme")
        try:
            signing_key = self._keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["aud", "exp", "iss", "tid"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Bearer token validation failed") from exc
        if claims.get("tid") != self._tenant_id:
            raise AuthenticationError("Bearer token tenant does not match the configured tenant")
        subject = claims.get("oid") or claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Bearer token does not include a user subject")
        return AuthenticatedUser(
            subject=subject,
            tenant_id=self._tenant_id,
            access_token=token,
        )
