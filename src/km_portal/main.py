from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import Response as BinaryResponse
from pydantic import BaseModel

from km_agents.artifacts import (
    ArtifactNotAvailableError,
    ArtifactStore,
    artifact_store_from_environment,
)
from km_agents.config import ConfigurationError
from km_agents.contracts import CaseStudyRequest, CaseStudyResponse, ImplementationKind
from km_agents.safety import validate_request

from .authentication import (
    AuthenticatedUser,
    AuthenticationError,
    EntraBearerTokenValidator,
)
from .gateway import (
    GatewayConfigurationError,
    GatewayExecutionError,
    OrchestrationGateway,
    gateway_from_environment,
)
from .uploads import (
    MAX_SOURCE_FILES,
    MAX_SOURCE_FILE_BYTES,
    MAX_TOTAL_SOURCE_BYTES,
    UploadValidationError,
    read_uploaded_sources,
)


class UserAuthenticator(Protocol):
    def authenticate(self, authorization: str | None) -> AuthenticatedUser: ...


@dataclass(frozen=True)
class PortalServices:
    authenticator: UserAuthenticator
    artifact_store: ArtifactStore
    gateway_factory: Callable[[CaseStudyRequest, str], OrchestrationGateway]

    @classmethod
    def from_environment(cls) -> "PortalServices":
        return cls(
            authenticator=EntraBearerTokenValidator.from_environment(),
            artifact_store=artifact_store_from_environment(),
            gateway_factory=gateway_from_environment,
        )


class CapabilityResponse(BaseModel):
    implementations: tuple[ImplementationKind, ...]
    supported_extensions: tuple[str, ...]
    max_source_files: int
    max_file_size_bytes: int
    max_total_source_size_bytes: int
    download_ttl_seconds: int


app = FastAPI(title="KM Agents Portal API", version="0.3.0")


def set_portal_services(services: PortalServices | None) -> None:
    app.state.portal_services = services


def _services() -> PortalServices:
    existing = getattr(app.state, "portal_services", None)
    if existing is not None:
        return existing
    try:
        services = PortalServices.from_environment()
    except (AuthenticationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KM portal identity and artifact delivery are not configured",
        ) from exc
    set_portal_services(services)
    return services


def _authenticated_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft Entra bearer authentication is required",
        )
    try:
        return _services().authenticator.authenticate(authorization)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft Entra bearer authentication failed",
        ) from exc


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    _services()
    return {"status": "ready"}


@app.get("/api/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        implementations=(
            ImplementationKind.PROMPT,
            ImplementationKind.HOSTED,
            ImplementationKind.WORKFLOW,
        ),
        supported_extensions=("docx", "pptx", "pdf", "xlsx"),
        max_source_files=MAX_SOURCE_FILES,
        max_file_size_bytes=MAX_SOURCE_FILE_BYTES,
        max_total_source_size_bytes=MAX_TOTAL_SOURCE_BYTES,
        download_ttl_seconds=15 * 60,
    )


@app.post("/api/case-studies", response_model=CaseStudyResponse)
async def create_case_study(
    request_json: Annotated[str, Form()],
    source_files: Annotated[list[UploadFile], File()],
    user: AuthenticatedUser = Depends(_authenticated_user),
) -> CaseStudyResponse:
    try:
        request = CaseStudyRequest.model_validate_json(request_json)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Case-study request metadata is invalid",
        ) from exc
    precheck = validate_request(request)
    if not precheck.approved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[finding.model_dump(mode="json") for finding in precheck.findings],
        )
    services = _services()
    try:
        sources = await read_uploaded_sources(source_files)
        gateway = services.gateway_factory(request, user.access_token)
        execution = gateway.invoke(request, sources)
        if not execution.response.validation.approved:
            return execution.response
        if not execution.artifact_name or not execution.artifact_content:
            raise GatewayExecutionError(
                "Foundry approved the request without returning a validated PowerPoint artifact"
            )
        reference = services.artifact_store.put(
            content=execution.artifact_content,
            name=execution.artifact_name,
            owner_subject=user.subject,
        )
        return execution.response.model_copy(update={"artifact": reference})
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more uploaded source files are invalid or exceed portal limits",
        ) from exc
    except (ConfigurationError, GatewayConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The selected Foundry orchestration gateway is not configured",
        ) from exc
    except GatewayExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The selected Foundry orchestration gateway did not return a compliant result",
        ) from exc


@app.get("/api/downloads/{artifact_id}")
def download_artifact(
    artifact_id: str,
    user: AuthenticatedUser = Depends(_authenticated_user),
) -> Response:
    try:
        artifact = _services().artifact_store.consume(artifact_id, user.subject)
    except ArtifactNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact is unavailable",
        ) from exc
    return BinaryResponse(
        content=artifact.content,
        media_type=artifact.reference.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.reference.name}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
