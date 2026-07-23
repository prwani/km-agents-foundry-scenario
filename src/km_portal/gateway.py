from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Protocol

from azure.ai.projects import AIProjectClient

from km_agents.contracts import (
    CaseStudyRequest,
    CaseStudyResponse,
    FindingCode,
    ValidationResult,
)
from km_agents.identity import TokenCredential, foundry_obo_credential

from .uploads import UploadedSource


class GatewayConfigurationError(ValueError):
    """Raised when a selected Foundry implementation cannot be invoked safely."""


class GatewayExecutionError(RuntimeError):
    """Raised when Foundry cannot produce a compliant, retrievable result."""


@dataclass(frozen=True)
class GatewayExecution:
    response: CaseStudyResponse
    artifact_name: str | None = None
    artifact_content: bytes | None = None


@dataclass(frozen=True)
class ContainerFileReference:
    container_id: str
    file_id: str
    filename: str


class OrchestrationGateway(Protocol):
    def invoke(
        self, request: CaseStudyRequest, sources: tuple[UploadedSource, ...]
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
            credential=credential,
        )
        self._agent_name = agent_name

    @classmethod
    def from_environment(cls, user_access_token: str) -> "PromptFoundryGateway":
        endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT"
        )
        agent_name = os.getenv("PROMPT_ORCHESTRATOR_AGENT_NAME")
        return cls(
            project_endpoint=endpoint or "",
            agent_name=agent_name or "",
            credential=foundry_obo_credential(user_access_token),
        )

    def invoke(
        self, request: CaseStudyRequest, sources: tuple[UploadedSource, ...]
    ) -> GatewayExecution:
        client = self._project.get_openai_client()
        uploaded_file_ids: list[str] = []
        generated_files: tuple[ContainerFileReference, ...] = ()
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
                    purpose="assistants",
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
            generated_files = _presentation_file_references(result)
            if not response.validation.approved:
                return GatewayExecution(response=response)
            _, artifact_name, artifact_content = _download_presentation(
                client, generated_files
            )
            return GatewayExecution(
                response=response,
                artifact_name=artifact_name,
                artifact_content=artifact_content,
            )
        finally:
            for file_id in uploaded_file_ids:
                client.files.delete(file_id)
            for artifact in generated_files:
                client.containers.files.delete(
                    artifact.file_id, container_id=artifact.container_id
                )


class WorkflowFoundryGateway:
    """Client-orchestrated sequential composition of the existing generator and
    validator Prompt agents, invoked directly (no orchestrator agent, no A2A tool).

    Foundry's A2A tool does not support Foundry-agent-to-Foundry-agent calls within
    the same project (see docs: the A2A tool is for calling agents hosted outside
    Foundry). This gateway reuses the same two already-provisioned specialist agents
    the orchestrator's A2A wiring targets, but drives the generate -> validate ->
    repair sequence from the portal process itself using the Responses API directly.
    This keeps the orchestrator/A2A stack untouched for future retesting once
    Foundry-to-Foundry A2A support lands.
    """

    _NO_RETRY_CODES = frozenset(
        {FindingCode.SENSITIVE_INFORMATION, FindingCode.CUSTOMER_NAME_NOT_APPROVED}
    )

    def __init__(
        self,
        project_endpoint: str,
        generator_agent_name: str,
        validator_agent_name: str,
        credential: TokenCredential | None = None,
        project_client: AIProjectClient | None = None,
        max_repair_attempts: int = 2,
    ) -> None:
        if not project_endpoint or not generator_agent_name or not validator_agent_name:
            raise GatewayConfigurationError(
                "Workflow Foundry project endpoint, generator, and validator agent "
                "names are required"
            )
        self._project = project_client or AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
        )
        self._generator_agent_name = generator_agent_name
        self._validator_agent_name = validator_agent_name
        self._max_repair_attempts = max_repair_attempts

    @classmethod
    def from_environment(cls, user_access_token: str) -> "WorkflowFoundryGateway":
        endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv(
            "AZURE_AI_PROJECT_ENDPOINT"
        )
        generator_agent_name = os.getenv(
            "WORKFLOW_GENERATOR_AGENT_NAME", "km-prompt-case-study-generator"
        )
        validator_agent_name = os.getenv(
            "WORKFLOW_VALIDATOR_AGENT_NAME", "km-prompt-validator"
        )
        return cls(
            project_endpoint=endpoint or "",
            generator_agent_name=generator_agent_name,
            validator_agent_name=validator_agent_name,
            credential=foundry_obo_credential(user_access_token),
            max_repair_attempts=int(os.getenv("MAX_REPAIR_ATTEMPTS", "2")),
        )

    def invoke(
        self, request: CaseStudyRequest, sources: tuple[UploadedSource, ...]
    ) -> GatewayExecution:
        client = self._project.get_openai_client()
        uploaded_file_ids: list[str] = []
        generated_files: tuple[ContainerFileReference, ...] = ()
        candidate: tuple[str, str, bytes] | None = None
        try:
            attempt = 0
            findings_feedback: str | None = None
            while True:
                generator_inputs = _generator_inputs(
                    request, sources, feedback=findings_feedback
                )
                for source in sources:
                    uploaded = client.files.create(
                        file=(source.name, source.content, source.content_type),
                        purpose="assistants",
                    )
                    uploaded_file_ids.append(uploaded.id)
                    generator_inputs.append(
                        {"type": "input_file", "file_id": uploaded.id}
                    )
                generation = client.responses.create(
                    input=[{"role": "user", "content": generator_inputs}],
                    extra_body={
                        "agent_reference": {
                            "name": self._generator_agent_name,
                            "type": "agent_reference",
                        }
                    },
                )
                generated_files = _presentation_file_references(generation)
                if not generated_files:
                    return GatewayExecution(
                        response=CaseStudyResponse(
                            implementation=request.implementation,
                            correlation_id=request.correlation_id,
                            status="rejected: generator did not produce a PPTX artifact",
                            validation=ValidationResult.rejected(
                                "Generator declined to produce a PPTX artifact "
                                "(likely business-sensitive source content).",
                            ),
                            repair_attempts=attempt,
                        )
                    )
                file_id, filename, content = _download_presentation(
                    client, generated_files
                )
                candidate = (file_id, filename, content)
                candidate_upload = client.files.create(
                    file=(
                        filename,
                        content,
                        "application/vnd.openxmlformats-officedocument"
                        ".presentationml.presentation",
                    ),
                    purpose="assistants",
                )
                uploaded_file_ids.append(candidate_upload.id)
                validation_result = client.responses.create(
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": _validator_instruction(request),
                                },
                                {
                                    "type": "input_file",
                                    "file_id": candidate_upload.id,
                                },
                            ],
                        }
                    ],
                    extra_body={
                        "agent_reference": {
                            "name": self._validator_agent_name,
                            "type": "agent_reference",
                        }
                    },
                )
                validation = _parse_validation_response(validation_result.output_text)
                if validation.approved:
                    return GatewayExecution(
                        response=CaseStudyResponse(
                            implementation=request.implementation,
                            correlation_id=request.correlation_id,
                            status="approved",
                            validation=validation,
                            repair_attempts=attempt,
                        ),
                        artifact_name=candidate[1],
                        artifact_content=candidate[2],
                    )
                blocking = {
                    finding.code
                    for finding in validation.findings
                    if finding.code in self._NO_RETRY_CODES
                }
                if blocking or attempt >= self._max_repair_attempts:
                    return GatewayExecution(
                        response=CaseStudyResponse(
                            implementation=request.implementation,
                            correlation_id=request.correlation_id,
                            status="rejected",
                            validation=validation,
                            repair_attempts=attempt,
                        )
                    )
                attempt += 1
                findings_feedback = "; ".join(validation.reasons) or "unspecified validation failure"
        finally:
            for file_id in uploaded_file_ids:
                client.files.delete(file_id)
            for artifact in generated_files:
                client.containers.files.delete(
                    artifact.file_id, container_id=artifact.container_id
                )


class HostedFoundryGateway:
    """Explicit boundary until the Foundry SDK exposes hosted session file APIs."""

    @classmethod
    def from_environment(cls, user_access_token: str) -> "HostedFoundryGateway":
        if not (
            os.getenv("FOUNDRY_PROJECT_ENDPOINT")
            and os.getenv("HOSTED_ORCHESTRATOR_AGENT_NAME")
        ):
            raise GatewayConfigurationError(
                "Hosted Foundry project endpoint and orchestrator name are required"
            )
        foundry_obo_credential(user_access_token)
        return cls()

    def invoke(
        self, request: CaseStudyRequest, sources: tuple[UploadedSource, ...]
    ) -> GatewayExecution:
        raise GatewayConfigurationError(
            "Hosted session file transfer is not configured. Create a Foundry hosted-session "
            "transfer adapter before accepting hosted portal requests."
        )


def gateway_from_environment(
    request: CaseStudyRequest, user_access_token: str
) -> OrchestrationGateway:
    if request.implementation.value == "prompt":
        return PromptFoundryGateway.from_environment(user_access_token)
    if request.implementation.value == "workflow":
        return WorkflowFoundryGateway.from_environment(user_access_token)
    return HostedFoundryGateway.from_environment(user_access_token)


def _orchestration_instruction(
    request: CaseStudyRequest, sources: tuple[UploadedSource, ...]
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
        "Generate and validate a case-study PPTX using the canonical template already attached "
        "to the generator agent and these uploaded source files. Never disclose raw source content. "
        "Return exactly one JSON object "
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


def _generator_inputs(
    request: CaseStudyRequest,
    sources: tuple[UploadedSource, ...],
    feedback: str | None = None,
) -> list[dict[str, Any]]:
    payload = {
        "customer_display_name": request.display_customer_name,
        "opportunity_summary": request.opportunity_summary,
        "audience": request.audience,
        "customer_name_approved_for_external_use": request.customer_name_approved_for_external_use,
        "correlation_id": request.correlation_id,
        "uploaded_files": [{"name": source.name, "kind": source.kind.value} for source in sources],
    }
    instruction = (
        "Generate a case-study PPTX using the canonical template already attached to you "
        "and the uploaded source files. Never disclose raw source content beyond what is "
        "appropriate for an external case study, and never include business-sensitive "
        "information. If the source content is too sensitive to summarize safely, "
        "decline and explain why in text instead of producing a PPTX.\n"
        f"Request: {json.dumps(payload, separators=(',', ':'))}"
    )
    if feedback:
        instruction += (
            "\nA previous draft was rejected by the validator agent for the following "
            f"reasons; produce a corrected draft that resolves them: {feedback}"
        )
    return [{"type": "input_text", "text": instruction}]


def _validator_instruction(request: CaseStudyRequest) -> str:
    payload = {
        "customer_display_name": request.display_customer_name,
        "customer_name_approved_for_external_use": request.customer_name_approved_for_external_use,
        "correlation_id": request.correlation_id,
    }
    return (
        "Validate the attached candidate case-study PPTX against the canonical template and "
        "sensitivity policy. Return only a single JSON object matching the shared "
        "ValidationResult schema (approved, findings, policy_version) with no other text.\n"
        f"Request: {json.dumps(payload, separators=(',', ':'))}"
    )


def _parse_validation_response(output_text: str) -> ValidationResult:
    try:
        return ValidationResult.model_validate_json(output_text)
    except ValueError as exc:
        raise GatewayExecutionError(
            "Foundry validator did not return the required structured ValidationResult"
        ) from exc


def _presentation_file_references(response: object) -> tuple[ContainerFileReference, ...]:
    model_dump = getattr(response, "model_dump", None)
    value = model_dump(mode="json") if callable(model_dump) else response
    references: list[ContainerFileReference] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            if item.get("type") == "container_file_citation":
                container_id = item.get("container_id")
                file_id = item.get("file_id")
                filename = item.get("filename")
                if (
                    isinstance(container_id, str)
                    and isinstance(file_id, str)
                    and isinstance(filename, str)
                    and filename.lower().endswith(".pptx")
                ):
                    references.append(
                        ContainerFileReference(
                            container_id=container_id,
                            file_id=file_id,
                            filename=filename,
                        )
                    )
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    unique_references: list[ContainerFileReference] = []
    seen: set[tuple[str, str, str]] = set()
    for reference in references:
        key = (reference.container_id, reference.file_id, reference.filename)
        if key not in seen:
            seen.add(key)
            unique_references.append(reference)
    return tuple(unique_references)


def _download_presentation(
    client: Any, references: tuple[ContainerFileReference, ...]
) -> tuple[str, str, bytes]:
    for reference in references:
        content = client.containers.files.content.retrieve(
            reference.file_id, container_id=reference.container_id
        ).read()
        if not isinstance(content, bytes) or not content.startswith(b"PK\x03\x04"):
            raise GatewayExecutionError("Foundry returned an invalid PowerPoint artifact")
        return reference.file_id, reference.filename, content
    raise GatewayExecutionError(
        "Foundry approved the request but did not provide a PowerPoint artifact"
    )
