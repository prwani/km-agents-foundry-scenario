from __future__ import annotations

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from km_agents.a2a import A2AConnection
from km_agents.config import ConfigurationError


def specialist_tools() -> tuple[object, object]:
    generator_connection_id = os.getenv("HOSTED_GENERATOR_A2A_CONNECTION_ID")
    validator_connection_id = os.getenv("HOSTED_VALIDATOR_A2A_CONNECTION_ID")
    if not generator_connection_id or not validator_connection_id:
        raise ConfigurationError(
            "Hosted generator and validator A2A project connection IDs are required"
        )
    return (
        A2AConnection(
            name="km-hosted-case-study-generator",
            project_connection_id=generator_connection_id,
            description="Creates a template-compliant case-study deck with Agent Framework Harness.",
        ).tool_definition(),
        A2AConnection(
            name="km-hosted-validator",
            project_connection_id=validator_connection_id,
            description="Validates template structure and sensitive-information policy.",
        ).tool_definition(),
    )


def create_orchestrator(client: FoundryChatClient) -> Agent:
    max_repairs = int(os.getenv("MAX_REPAIR_ATTEMPTS", "2"))
    if max_repairs != 2:
        raise ConfigurationError("MAX_REPAIR_ATTEMPTS must remain 2 for the approved policy")
    return Agent(
        client=client,
        name="km-hosted-orchestrator",
        instructions=(
            "Route every case-study request to the hosted generator, then to the hosted validator. "
            "Return an artifact only after validation approves it. Permit at most two clean repair "
            "attempts. A sensitivity finding requires deleting the artifact and regenerating from "
            "scratch. Fail closed when either specialist fails or returns inconclusive evidence."
        ),
        tools=list(specialist_tools()),
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
    ResponsesHostServer(create_orchestrator(client)).run()


if __name__ == "__main__":
    main()
