from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from km_agents.contracts import CaseStudyRequest, ImplementationKind
from km_agents.safety import validate_request


class CapabilityResponse(BaseModel):
    implementations: tuple[ImplementationKind, ...]
    supported_extensions: tuple[str, ...]
    max_source_files: int
    max_file_size_bytes: int
    max_total_source_size_bytes: int
    download_ttl_seconds: int


app = FastAPI(title="KM Agents Portal API", version="0.2.0")


def _require_authenticated_user(client_principal_id: str | None) -> str:
    if not client_principal_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft Entra authentication is required",
        )
    return client_principal_id


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        implementations=(ImplementationKind.PROMPT, ImplementationKind.HOSTED),
        supported_extensions=("docx", "pptx", "pdf", "xlsx"),
        max_source_files=10,
        max_file_size_bytes=20 * 1024 * 1024,
        max_total_source_size_bytes=75 * 1024 * 1024,
        download_ttl_seconds=15 * 60,
    )


@app.post("/api/case-studies")
def create_case_study(
    request: CaseStudyRequest,
    x_ms_client_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    _require_authenticated_user(x_ms_client_principal_id)
    precheck = validate_request(request)
    if not precheck.approved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[finding.model_dump(mode="json") for finding in precheck.findings],
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            f"The {request.implementation.value} Foundry orchestration gateway is not configured. "
            "Set the deployed orchestrator name and project endpoint before accepting requests."
        ),
    )
