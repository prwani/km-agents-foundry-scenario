from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from typing import Protocol
from urllib.parse import urlparse

import httpx
from azure.identity import OnBehalfOfCredential

from km_agents.contracts import SourceArtifact, SourceFileKind

from .authentication import AuthenticatedUser


class SourceRetrievalError(ValueError):
    """Raised when an explicit Microsoft 365 source cannot be safely retrieved."""


@dataclass(frozen=True)
class RetrievedSource:
    name: str
    kind: SourceFileKind
    content_type: str
    content: bytes
    source_url: str


class GraphHttpClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


class MicrosoftGraphSourceResolver:
    GRAPH_SCOPE = "https://graph.microsoft.com/.default"
    GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        http_client: GraphHttpClient | None = None,
    ) -> None:
        if not tenant_id or not client_id or not client_secret:
            raise ValueError("Entra tenant ID, client ID, and client secret are required for OBO")
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or httpx.Client(follow_redirects=True, timeout=30.0)

    @classmethod
    def from_environment(cls) -> "MicrosoftGraphSourceResolver":
        tenant_id = os.getenv("ENTRA_TENANT_ID")
        client_id = os.getenv("ENTRA_PORTAL_CLIENT_ID")
        client_secret = os.getenv("ENTRA_CLIENT_SECRET")
        if not tenant_id or not client_id or not client_secret:
            raise SourceRetrievalError(
                "ENTRA_TENANT_ID, ENTRA_PORTAL_CLIENT_ID, and ENTRA_CLIENT_SECRET are required for OBO"
            )
        return cls(tenant_id, client_id, client_secret)

    def retrieve(self, user: AuthenticatedUser, artifact: SourceArtifact) -> RetrievedSource:
        return self._retrieve(user, artifact, max_size_bytes=20 * 1024 * 1024)

    def retrieve_template(self, user: AuthenticatedUser, template_url: str) -> RetrievedSource:
        return self._retrieve(
            user,
            SourceArtifact(url=template_url, kind=SourceFileKind.PPTX),
            max_size_bytes=25 * 1024 * 1024,
        )

    def _retrieve(
        self,
        user: AuthenticatedUser,
        artifact: SourceArtifact,
        max_size_bytes: int,
    ) -> RetrievedSource:
        url = str(artifact.url)
        self._validate_microsoft_365_url(url)
        token = self._graph_token(user.access_token)
        headers = {"Authorization": f"Bearer {token}"}
        share_id = self._share_id(url)
        metadata = self._http.get(
            f"{self.GRAPH_ROOT}/shares/{share_id}/driveItem",
            headers=headers,
            params={"$select": "id,name,size,file,webUrl"},
        )
        self._raise_for_status(metadata, "resolve source")
        payload = metadata.json()
        name = payload.get("name")
        size = payload.get("size")
        if not isinstance(name, str) or not isinstance(size, int):
            raise SourceRetrievalError("Microsoft Graph returned incomplete source metadata")
        self._validate_name_and_size(
            name,
            artifact.kind,
            size,
            artifact.size_bytes,
            max_size_bytes,
        )
        content = self._http.get(
            f"{self.GRAPH_ROOT}/shares/{share_id}/driveItem/content",
            headers=headers,
        )
        self._raise_for_status(content, "download source")
        if len(content.content) != size or len(content.content) > max_size_bytes:
            raise SourceRetrievalError("Downloaded source content does not match approved size limits")
        self._validate_content_signature(content.content, artifact.kind)
        return RetrievedSource(
            name=name,
            kind=artifact.kind,
            content_type=content.headers.get("content-type", "application/octet-stream"),
            content=content.content,
            source_url=url,
        )

    def _graph_token(self, user_assertion: str) -> str:
        credential = OnBehalfOfCredential(
            tenant_id=self._tenant_id,
            client_id=self._client_id,
            client_secret=self._client_secret,
            user_assertion=user_assertion,
        )
        return credential.get_token(self.GRAPH_SCOPE).token

    @staticmethod
    def _share_id(url: str) -> str:
        encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
        return f"u!{encoded}"

    @staticmethod
    def _validate_microsoft_365_url(url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (
            host.endswith(".sharepoint.com") or host in {"1drv.ms", "onedrive.live.com"}
        ):
            raise SourceRetrievalError(
                "Source URLs must be HTTPS SharePoint or OneDrive links"
            )

    @staticmethod
    def _validate_name_and_size(
        name: str,
        kind: SourceFileKind,
        actual_size: int,
        declared_size: int | None,
        max_size_bytes: int,
    ) -> None:
        if not name.lower().endswith(f".{kind.value}"):
            raise SourceRetrievalError("Source file extension does not match the declared file kind")
        if actual_size < 1 or actual_size > max_size_bytes:
            raise SourceRetrievalError("Source file exceeds the configured size limit")
        if declared_size is not None and actual_size != declared_size:
            raise SourceRetrievalError("Source file size differs from the request declaration")

    @staticmethod
    def _validate_content_signature(content: bytes, kind: SourceFileKind) -> None:
        if kind == SourceFileKind.PDF and not content.startswith(b"%PDF-"):
            raise SourceRetrievalError("Downloaded source does not have a valid PDF signature")
        if kind in {SourceFileKind.DOCX, SourceFileKind.PPTX, SourceFileKind.XLSX} and not content.startswith(
            b"PK\x03\x04"
        ):
            raise SourceRetrievalError("Downloaded source does not have a valid Office package signature")

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SourceRetrievalError(f"Microsoft Graph could not {operation}") from exc
