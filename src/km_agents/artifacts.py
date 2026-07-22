from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import secrets
from threading import Lock
from typing import Protocol

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError, ResourceModifiedError

from .contracts import ArtifactReference
from .identity import azure_credential


SUPPORTED_POWERPOINT_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
}

MAX_ARTIFACT_BYTES = 25 * 1024 * 1024


class ArtifactNotAvailableError(ValueError):
    """Raised for expired, consumed, missing, or unauthorized artifact requests."""


@dataclass(frozen=True)
class DownloadableArtifact:
    reference: ArtifactReference
    content: bytes


class ArtifactStore(Protocol):
    def put(self, content: bytes, name: str, owner_subject: str) -> ArtifactReference: ...

    def consume(self, artifact_id: str, owner_subject: str) -> DownloadableArtifact: ...


def create_powerpoint_reference(path: Path, name: str, ttl_minutes: int = 15) -> ArtifactReference:
    if not path.is_file():
        raise FileNotFoundError(f"PowerPoint artifact is missing: {path}")
    if not name.lower().endswith((".pptx", ".ppt")):
        raise ValueError("PowerPoint artifact name must end with .pptx or .ppt")
    if ttl_minutes < 1 or ttl_minutes > 60:
        raise ValueError("PowerPoint artifact TTL must be between 1 and 60 minutes")
    content = path.read_bytes()
    return _create_reference(content=content, name=name, ttl_minutes=ttl_minutes)


def _create_reference(content: bytes, name: str, ttl_minutes: int = 15) -> ArtifactReference:
    if len(content) > MAX_ARTIFACT_BYTES:
        raise ValueError("PowerPoint artifact cannot exceed 25 MB")
    return ArtifactReference(
        artifact_id=secrets.token_urlsafe(32),
        name=name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        single_use=True,
    )


class InMemoryArtifactStore:
    """Development/test store; production must use BlobArtifactStore."""

    def __init__(self, owner_hash_salt: str) -> None:
        if not owner_hash_salt:
            raise ValueError("Artifact owner hash salt is required")
        self._owner_hash_salt = owner_hash_salt
        self._entries: dict[str, tuple[ArtifactReference, str, bytes]] = {}
        self._lock = Lock()

    def put(self, content: bytes, name: str, owner_subject: str) -> ArtifactReference:
        reference = _create_reference(content=content, name=name)
        with self._lock:
            self._entries[reference.artifact_id] = (
                reference,
                _owner_hash(owner_subject, self._owner_hash_salt),
                content,
            )
        return reference

    def consume(self, artifact_id: str, owner_subject: str) -> DownloadableArtifact:
        with self._lock:
            entry = self._entries.get(artifact_id)
            if not entry:
                raise ArtifactNotAvailableError("Artifact is unavailable or was already consumed")
            reference, owner_hash, content = entry
            if reference.expires_at <= datetime.now(timezone.utc):
                self._entries.pop(artifact_id, None)
                raise ArtifactNotAvailableError("Artifact download has expired")
            if not hmac.compare_digest(
                owner_hash, _owner_hash(owner_subject, self._owner_hash_salt)
            ):
                raise ArtifactNotAvailableError("Artifact is unavailable")
            self._entries.pop(artifact_id)
        return DownloadableArtifact(reference=reference, content=content)


class BlobArtifactStore:
    def __init__(
        self,
        endpoint: str,
        container_name: str,
        owner_hash_salt: str,
        blob_service: BlobServiceClient | None = None,
    ) -> None:
        if not endpoint.startswith("https://") or not container_name or not owner_hash_salt:
            raise ValueError("Blob endpoint, container name, and owner hash salt are required")
        self._container = container_name
        self._owner_hash_salt = owner_hash_salt
        self._service = blob_service or BlobServiceClient(
            account_url=endpoint,
            credential=azure_credential(),
        )

    def put(self, content: bytes, name: str, owner_subject: str) -> ArtifactReference:
        reference = _create_reference(content=content, name=name)
        blob = self._service.get_blob_client(
            container=self._container,
            blob=f"case-studies/{reference.artifact_id}.pptx",
        )
        metadata = {
            "owner_hash": _owner_hash(owner_subject, self._owner_hash_salt),
            "expires_at": reference.expires_at.isoformat(),
            "artifact_name": reference.name,
        }
        try:
            blob.upload_blob(content, overwrite=False, metadata=metadata)
        except ResourceExistsError as exc:
            raise RuntimeError("Generated artifact identifier collision") from exc
        return reference

    def consume(self, artifact_id: str, owner_subject: str) -> DownloadableArtifact:
        blob = self._service.get_blob_client(
            container=self._container,
            blob=f"case-studies/{artifact_id}.pptx",
        )
        try:
            lease = blob.acquire_lease(15)
            properties = blob.get_blob_properties(lease=lease)
            metadata = properties.metadata
            try:
                expires_at = datetime.fromisoformat(metadata["expires_at"])
                artifact_name = metadata["artifact_name"]
            except (KeyError, ValueError) as exc:
                raise ArtifactNotAvailableError("Artifact is unavailable") from exc
            if not isinstance(artifact_name, str) or not artifact_name:
                raise ArtifactNotAvailableError("Artifact is unavailable")
            expected_owner = _owner_hash(owner_subject, self._owner_hash_salt)
            if expires_at <= datetime.now(timezone.utc):
                blob.delete_blob(lease=lease)
                raise ArtifactNotAvailableError("Artifact download has expired")
            if not hmac.compare_digest(metadata.get("owner_hash", ""), expected_owner):
                raise ArtifactNotAvailableError("Artifact is unavailable")
            content = blob.download_blob(lease=lease).readall()
            if len(content) > MAX_ARTIFACT_BYTES:
                blob.delete_blob(lease=lease)
                raise ArtifactNotAvailableError("Artifact is unavailable")
            blob.delete_blob(lease=lease)
        except (ResourceNotFoundError, ResourceModifiedError) as exc:
            raise ArtifactNotAvailableError(
                "Artifact is unavailable or was already consumed"
            ) from exc
        return DownloadableArtifact(
            reference=ArtifactReference(
                artifact_id=artifact_id,
                name=artifact_name,
                content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                expires_at=expires_at,
                single_use=True,
            ),
            content=content,
        )


def artifact_store_from_environment() -> ArtifactStore:
    mode = os.getenv("ARTIFACT_STORAGE_MODE", "blob").lower()
    salt = os.getenv("ARTIFACT_OWNER_HASH_SALT")
    if not salt:
        raise ValueError("ARTIFACT_OWNER_HASH_SALT is required")
    if mode == "blob":
        endpoint = os.getenv("AZURE_STORAGE_BLOB_ENDPOINT")
        container = os.getenv("ARTIFACT_CONTAINER_NAME")
        if not endpoint or not container:
            raise ValueError(
                "AZURE_STORAGE_BLOB_ENDPOINT and ARTIFACT_CONTAINER_NAME are required"
            )
        return BlobArtifactStore(endpoint, container, salt)
    if mode == "memory" and os.getenv("KM_AGENTS_ENVIRONMENT") == "development":
        return InMemoryArtifactStore(salt)
    raise ValueError("Only Blob artifact storage is allowed outside development")


def _owner_hash(owner_subject: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}\x00{owner_subject}".encode("utf-8")).hexdigest()
