from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from km_agents.contracts import SourceFileKind


MAX_SOURCE_FILES = 10
MAX_SOURCE_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 75 * 1024 * 1024

CONTENT_TYPES = {
    SourceFileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    SourceFileKind.PDF: "application/pdf",
    SourceFileKind.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    SourceFileKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class UploadValidationError(ValueError):
    """Raised when an uploaded source is not within the approved portal boundary."""


@dataclass(frozen=True)
class UploadedSource:
    name: str
    kind: SourceFileKind
    content_type: str
    content: bytes


async def read_uploaded_sources(files: list[UploadFile]) -> tuple[UploadedSource, ...]:
    if not files or len(files) > MAX_SOURCE_FILES:
        raise UploadValidationError(f"Upload between 1 and {MAX_SOURCE_FILES} source files")
    sources: list[UploadedSource] = []
    total_size = 0
    for file in files:
        try:
            source = await _read_upload(file)
        finally:
            await file.close()
        total_size += len(source.content)
        if total_size > MAX_TOTAL_SOURCE_BYTES:
            raise UploadValidationError("Combined uploaded source size cannot exceed 75 MB")
        sources.append(source)
    return tuple(sources)


async def _read_upload(file: UploadFile) -> UploadedSource:
    name = file.filename or ""
    if not name or Path(name).name != name:
        raise UploadValidationError("Uploaded source filename is invalid")
    suffix = Path(name).suffix.lower().removeprefix(".")
    try:
        kind = SourceFileKind(suffix)
    except ValueError as exc:
        raise UploadValidationError(
            "Uploaded sources must be DOCX, PPTX, PDF, or XLSX files"
        ) from exc
    content = await file.read(MAX_SOURCE_FILE_BYTES + 1)
    if not content or len(content) > MAX_SOURCE_FILE_BYTES:
        raise UploadValidationError("Uploaded source exceeds the 20 MB size limit")
    _validate_content_signature(content, kind)
    return UploadedSource(
        name=name,
        kind=kind,
        content_type=CONTENT_TYPES[kind],
        content=content,
    )


def _validate_content_signature(content: bytes, kind: SourceFileKind) -> None:
    if kind == SourceFileKind.PDF and not content.startswith(b"%PDF-"):
        raise UploadValidationError("Uploaded PDF does not have a valid signature")
    if kind in {SourceFileKind.DOCX, SourceFileKind.PPTX, SourceFileKind.XLSX} and not content.startswith(
        b"PK\x03\x04"
    ):
        raise UploadValidationError("Uploaded Office file does not have a valid package signature")
