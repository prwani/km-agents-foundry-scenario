from __future__ import annotations

from dataclasses import dataclass

from agent_framework.foundry import FoundryChatClient

from .config import ConfigurationError


@dataclass(frozen=True)
class A2AConnection:
    name: str
    project_connection_id: str
    description: str

    def tool_definition(self) -> object:
        if not self.name:
            raise ConfigurationError("A2A connection name is required")
        if not self.project_connection_id.startswith("/subscriptions/"):
            raise ConfigurationError(
                f"A2A project connection ID for {self.name} must be a fully qualified Azure resource ID"
            )
        return FoundryChatClient.get_a2a_tool(
            project_connection_id=self.project_connection_id
        )
