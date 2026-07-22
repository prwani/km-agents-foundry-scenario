from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agent_framework import FileSystemAgentFileStore, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from km_agents.config import ConfigurationError
from km_agents.workiq import WorkIqConnection


def create_generator_harness(client: Any) -> Any:
    skill_path = Path(os.getenv("PPTX_SKILL_PATH", "skills/pptx")).resolve()
    if not (skill_path / "SKILL.md").is_file():
        raise ConfigurationError(f"PowerPoint skill is missing: {skill_path / 'SKILL.md'}")

    workspace = Path(os.getenv("AGENT_WORKSPACE_ROOT", str(Path.home() / "data"))).resolve()
    work_iq_id = os.getenv("WORK_IQ_PROJECT_CONNECTION_ID")
    if not work_iq_id:
        raise ConfigurationError("WORK_IQ_PROJECT_CONNECTION_ID is required")
    WorkIqConnection(work_iq_id).toolbox_shape()
    work_iq_tool = FoundryChatClient.get_a2a_tool(project_connection_id=work_iq_id)

    return create_harness_agent(
        client=client,
        name="km-hosted-case-study-generator",
        agent_instructions=(
            "Generate an eight-slide Contoso Limited case-study deck from user-authorized files "
            "under input/. Use Work IQ only for the explicit source URLs in the request. Use the "
            "approved PowerPoint skill, preserve every protected template element, and write one "
            "PPTX under output/. Never invent evidence or include sensitive source facts."
        ),
        tools=[work_iq_tool],
        skills_paths=[str(skill_path)],
        file_access_store=FileSystemAgentFileStore(workspace),
        disable_web_search=True,
        disable_tool_auto_approval=True,
        disable_file_memory=True,
        background_agents=None,
        shell_executor=None,
        loop_max_iterations=int(os.getenv("HARNESS_MAX_ITERATIONS", "3")),
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
    ResponsesHostServer(create_generator_harness(client)).run()


if __name__ == "__main__":
    main()
