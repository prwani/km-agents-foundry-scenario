from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agent_framework import (
    FileSystemAgentFileStore,
    InMemoryHistoryProvider,
    create_harness_agent,
)
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from km_agents.agents.hosted.case_study_generator.validation import (
    validate_case_study_deck_tool,
)
from km_agents.agents.hosted.case_study_generator.operations import (
    create_case_study_deck_tool,
    extract_uploaded_evidence_tool,
)
from km_agents.config import ConfigurationError


def _max_repair_attempts() -> int:
    max_repairs = int(os.getenv("MAX_REPAIR_ATTEMPTS", "2"))
    if max_repairs != 2:
        raise ConfigurationError("MAX_REPAIR_ATTEMPTS must remain 2 for the approved policy")
    return max_repairs


def create_generator_harness(client: Any) -> Any:
    skill_path = Path(os.getenv("PPTX_SKILL_PATH", "skills/pptx")).resolve()
    if not (skill_path / "SKILL.md").is_file():
        raise ConfigurationError(f"PowerPoint skill is missing: {skill_path / 'SKILL.md'}")
    template_path = Path(
        os.getenv("CASE_STUDY_TEMPLATE_PATH", "assets/templates/contoso-case-study-template.pptx")
    ).resolve()
    if not template_path.is_file():
        raise ConfigurationError(f"Canonical PowerPoint template is missing: {template_path}")
    brand_guidelines_path = Path(
        os.getenv(
            "CASE_STUDY_BRAND_GUIDELINES_PATH",
            "assets/templates/contoso-case-study-template-with-brand-guidelines.pptx",
        )
    ).resolve()
    if not brand_guidelines_path.is_file():
        raise ConfigurationError(f"Contoso brand-guidelines template is missing: {brand_guidelines_path}")

    workspace = Path(os.getenv("AGENT_WORKSPACE_ROOT", str(Path.home() / "data"))).resolve()
    max_repairs = _max_repair_attempts()

    return create_harness_agent(
        client=client,
        name="km-hosted-case-study-agent",
        agent_instructions=(
            "Complete the entire case-study workflow yourself. Generate an eight-slide Contoso "
            f"Limited case-study deck from user-uploaded files under input/ using the canonical "
            f"template at {template_path} and follow the Contoso brand-guidelines reference at "
            f"{brand_guidelines_path}. The output contains only the eight canonical case-study "
            "slides, not the reference deck's guidance slides. Preserve the template typography, "
            "approved palette and contrast, safe margins, flat visual style, source-labelled "
            "data treatment, and clear, credible, human, responsible voice. First call "
            "extract_uploaded_evidence for every source "
            "file, then use only the extracted evidence to populate every field of the "
            "generate_case_study_deck content schema. When the request does not approve the "
            "customer name, use Customer and never place the raw customer name in any content field. "
            "For every content field, use direct source statements only; otherwise use Evidence pending. "
            "The template requires three architecture entries, four implementation steps, three outcomes, "
            "and two next steps; repeat Evidence pending for any unsupported required slot. "
            "Call generate_case_study_deck with the original request JSON to create one PPTX under output/, preserving every protected "
            "template element. Never invent evidence or include sensitive source facts. After every "
            "generation or repair, call validate_case_study_deck with the deck's workspace-relative "
            "path, the original request JSON, and every input source path. Return a deck only when the deterministic result "
            "is approved. For a failed validation, repair only from the supplied evidence and retry "
            f"at most {max_repairs} times. If the original request JSON is missing, validation is "
            "inconclusive, reports sensitive information, or remains unsuccessful, delete the "
            "draft and fail closed without returning a deck."
        ),
        tools=[
            extract_uploaded_evidence_tool,
            create_case_study_deck_tool,
            validate_case_study_deck_tool,
        ],
        history_provider=InMemoryHistoryProvider(load_messages=False),
        skills_paths=[str(skill_path)],
        file_access_store=FileSystemAgentFileStore(workspace),
        file_access_disable_readonly_tool_approval=True,
        file_access_disable_write_tool_approval=True,
        disable_web_search=True,
        disable_tool_auto_approval=True,
        disable_file_memory=True,
        background_agents=None,
        shell_executor=None,
        loop_max_iterations=int(os.getenv("HARNESS_MAX_ITERATIONS", "3")),
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
    ResponsesHostServer(create_generator_harness(client)).run()


if __name__ == "__main__":
    main()
