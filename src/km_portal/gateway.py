from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Protocol

from azure.ai.projects import AIProjectClient

from km_agents.contracts import CaseStudyRequest, CaseStudyResponse
from km_agents.identity import TokenCredential, azure_credential

from .graph import RetrievedSource


class GatewayConfigurationError(ValueError):
    """Raised when a selected Foundry implementation cannot be invoked safely."""


class GatewayExecutionError(RuntimeError):
    """Raised when Foundry cannot produce a compliant, retrievable result."""


@dataclass(frozen=True)
class GatewayExecution:
    response: CaseStudyResponse
    artifact_name: str | None = None
    artifact_content: bytes | None = None


class OrchestrationGateway(Protocol):
    def invoke(
        self, request: CaseStudyRequest, sources: tuple[RetrievedSource, ...]
    ) -> GatewayExecution: ...


class PromptFoundryGateway:
    def __init__(
        self,
        project_endpoint: str,
        agent_name: str,
        credential: TokenCredential | None = None,
        project_client: AIProjectClient | None = None,
    ) -> None:
        if not project_endpoint or not agent_name:
            raise GatewayConfigurationError(
                "Prompt Foundry project endpoint and orchestrator name are required"
            )
        self._project = project_client or AIProjectClient(
            endpoint=project_endpoint,
            credential=credential or azure_credential(),
        )
        self._agent_name = agent_name

    @classmethod
    def from_environment(cls) -> "PromptFoundryGateway":
        endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT"
        )
        agent_name = os.getenv("PROMPT_ORCHESTRATOR_AGENT_NAME")
        return cls(project_endpoint=endpoint or "", agent_name=agent_name or "")

    def invoke(
        self, request: CaseStudyRequest, sources: tuple[RetrievedSource, ...]
    ) -> GatewayExecution:
        client = self._project.get_openai_client()
        uploaded_file_ids: list[str] = []
        generated_file_ids: set[str] = set()
        try:
            inputs: list[dict[str, Any]] = [
                {
                    "type": "input_text",
                    "text": _orchestration_instruction(request, sources),
                }
            ]
            for source in sources:
                uploaded = client.files.create(
                    file=(source.name, source.content, source.content_type),
                    purpose="user_data",
                )
                uploaded_file_ids.append(uploaded.id)
                inputs.append({"type": "input_file", "file_id": uploaded.id})
            result = client.responses.create(
                input=[{"role": "user", "content": inputs}],
                extra_body={
                    "agent_reference": {
                        "name": self._agent_name,
                        "type": "agent_reference",
                    }
                },
            )
            response = _parse_orchestrator_response(result.output_text, request)
            generated_file_ids = _file_ids_from_response(result)
            if not response.validation.approved:
                return GatewayExecution(response=response)
            _, artifact_name, artifact_content = _download_presentation(
                client, generated_file_ids
            )
            return GatewayExecution(
                response=response,
                artifact_name=artifact_name,
                artifact_content=artifact_content,
            )
        finally:
            for file_id in [*uploaded_file_ids, *generated_file_ids]:
                client.files.delete(file_id)


class HostedFoundryGateway:
    """Explicit boundary until the Foundry SDK exposes hosted session file APIs."""

    @classmethod
    def from_environment(cls) -> "HostedFoundryGateway":
        if not (
            os.getenv("FOUNDRY_PROJECT_ENDPOINT")
            and os.getenv("HOSTED_ORCHESTRATOR_AGENT_NAME")
        ):
            raise GatewayConfigurationError(
                "Hosted Foundry project endpoint and orchestrator name are required"
            )
        return cls()

    def invoke(
        self, request: CaseStudyRequest, sources: tuple[RetrievedSource, ...]
    ) -> GatewayExecution:
        raise GatewayConfigurationError(
            "Hosted session file transfer is not configured. Create a Foundry hosted-session "
            "transfer adapter before accepting hosted portal requests."
        )


def gateway_from_environment(request: CaseStudyRequest) -> OrchestrationGateway:
    if request.implementation.value == "prompt":
        return PromptFoundryGateway.from_environment()
    return HostedFoundryGateway.from_environment()


def _orchestration_instruction(
    request: CaseStudyRequest, sources: tuple[RetrievedSource, ...]
) -> str:
    payload = {
        "implementation": request.implementation.value,
        "customer_display_name": request.display_customer_name,
        "opportunity_summary": request.opportunity_summary,
        "audience": request.audience,
        "customer_name_approved_for_external_use": request.customer_name_approved_for_external_use,
        "correlation_id": request.correlation_id,
        "uploaded_files": [{"name": source.name, "kind": source.kind.value} for source in sources],
    }
    return (
        "Generate and validate a case-study PPTX using the uploaded canonical template and "
        "source files. Never disclose raw source content or URLs. Return exactly one JSON object "
        "matching CaseStudyResponse without an artifact field. If validation is not approved, "
        "return a rejected response and do not create a downloadable artifact.\n"
        f"Request: {json.dumps(payload, separators=(',', ':'))}"
    )


def _parse_orchestrator_response(
    output_text: str, request: CaseStudyRequest
) -> CaseStudyResponse:
    try:
        response = CaseStudyResponse.model_validate_json(output_text)
    except ValueError as exc:
        raise GatewayExecutionError(
            "Foundry orchestrator did not return the required structured response"
        ) from exc
    if response.implementation != request.implementation:
        raise GatewayExecutionError("Foundry response implementation does not match the request")
    if response.correlation_id != request.correlation_id:
        raise GatewayExecutionError("Foundry response correlation ID does not match the request")
    if response.artifact is not None:
        raise GatewayExecutionError(
            "Foundry must not expose artifact URLs or file identifiers through the portal response"
        )
    return response


def _file_ids_from_response(response: object) -> set[str]:
    model_dump = getattr(response, "model_dump", None)
    value = model_dump(mode="json") if callable(model_dump) else response
    file_ids: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if key == "file_id" and isinstance(nested, str):
                    file_ids.add(nested)
                else:
                    visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return file_ids


def _download_presentation(client: Any, file_ids: set[str]) -> tuple[str, str, bytes]:
    for file_id in sorted(file_ids):
        metadata = client.files.retrieve(file_id)
        name = getattr(metadata, "filename", "")
        if isinstance(name, str) and name.lower().endswith(".pptx"):
            content = client.files.content(file_id).read()
            if not isinstance(content, bytes) or not content.startswith(b"PK\x03\x04"):
                raise GatewayExecutionError("Foundry returned an invalid PowerPoint artifact")
            return file_id, name, content
    raise GatewayExecutionError(
        "Foundry approved the request but did not provide a PowerPoint artifact"
    )
