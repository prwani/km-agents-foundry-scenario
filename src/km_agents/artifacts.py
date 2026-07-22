from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import secrets

from .contracts import ArtifactReference


SUPPORTED_POWERPOINT_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
}


def create_powerpoint_reference(path: Path, name: str, ttl_minutes: int = 15) -> ArtifactReference:
    if not path.is_file():
        raise FileNotFoundError(f"PowerPoint artifact is missing: {path}")
    if not name.lower().endswith((".pptx", ".ppt")):
        raise ValueError("PowerPoint artifact name must end with .pptx or .ppt")
    if ttl_minutes < 1 or ttl_minutes > 60:
        raise ValueError("PowerPoint artifact TTL must be between 1 and 60 minutes")
    content = path.read_bytes()
    return ArtifactReference(
        artifact_id=secrets.token_urlsafe(32),
        name=name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        single_use=True,
    )
