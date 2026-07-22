from __future__ import annotations

import os
from pathlib import Path

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from km_agents.config import ConfigurationError
from km_agents.contracts import CaseStudyRequest, ValidationResult
from km_agents.pptx_skill.validation import validate_presentation


def _workspace_file(relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Deck path must be relative to the hosted session workspace")
    workspace = Path(os.getenv("AGENT_WORKSPACE_ROOT", str(Path.home() / "data"))).resolve()
    candidate = (workspace / relative_path).resolve()
    if workspace not in candidate.parents or candidate.suffix.lower() != ".pptx":
        raise ValueError("Deck path must resolve to a PPTX inside the hosted session workspace")
    if not candidate.is_file():
        raise FileNotFoundError(f"Deck is missing from the hosted session workspace: {relative_path}")
    return candidate


def validate_case_study_deck(
    deck_path: Path,
    request: CaseStudyRequest,
) -> ValidationResult:
    policy_path = Path(
        os.getenv("TEMPLATE_POLICY_PATH", "assets/templates/contoso-template-policy.json")
    )
    return validate_presentation(deck_path=deck_path, policy_path=policy_path, request=request)


@tool(
    name="validate_case_study_deck",
    description="Deterministically validate a session PPTX against the canonical template and safety policy.",
)
def validate_case_study_deck_tool(relative_deck_path: str, request_json: str) -> str:
    request = CaseStudyRequest.model_validate_json(request_json)
    result = validate_case_study_deck(_workspace_file(relative_deck_path), request)
    return result.model_dump_json()


def create_validator(client: FoundryChatClient) -> Agent:
    return Agent(
        client=client,
        name="km-hosted-validator",
        instructions=(
            "Always call validate_case_study_deck exactly once with the generated session PPTX and "
            "the original request JSON. Approve only when the deterministic result is approved and "
            "your review finds no sensitivity or disclosure uncertainty. Never turn an inconclusive "
            "or failed tool result into approval. Return the structured validation result only."
        ),
        tools=[validate_case_study_deck_tool],
        default_options={"store": False},
    )


def main() -> None:
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    model = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if not endpoint or not model:
        raise ConfigurationError(
            "FOUNDRY_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME are required"
        )
    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=endpoint,
        model=model,
        credential=credential,
    )
    ResponsesHostServer(create_validator(client)).run()


if __name__ == "__main__":
    main()
