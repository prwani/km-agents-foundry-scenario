import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from azure.ai.projects.models import A2APreviewTool

from km_agents.a2a import A2AConnection
from km_agents.config import ConfigurationError
from km_agents.agents.hosted.case_study_generator import main as generator
from km_agents.agents.hosted.orchestrator import main as orchestrator
from km_agents.agents.hosted.validator import main as validator


ROOT = pathlib.Path(__file__).resolve().parents[1]


class HostedAgentTests(unittest.TestCase):
    def test_a2a_connection_requires_fully_qualified_resource_id(self):
        connection = A2AConnection("generator", "https://example.test/a2a", "generator")
        with self.assertRaises(ConfigurationError):
            connection.tool_definition()

    def test_orchestrator_builds_two_foundry_a2a_tools(self):
        with patch.dict(
            os.environ,
            {
                "HOSTED_GENERATOR_A2A_CONNECTION_ID": "/subscriptions/test/connections/generator",
                "HOSTED_VALIDATOR_A2A_CONNECTION_ID": "/subscriptions/test/connections/validator",
            },
            clear=False,
        ):
            tools = orchestrator.specialist_tools()
        self.assertEqual(len(tools), 2)
        self.assertTrue(all(isinstance(item, A2APreviewTool) for item in tools))

    def test_generator_harness_is_scoped_and_unsafe_capabilities_are_disabled(self):
        captured = {}

        def fake_harness(**kwargs):
            captured.update(kwargs)
            return "agent"

        with tempfile.TemporaryDirectory() as workspace, patch.dict(
            os.environ,
            {
                "PPTX_SKILL_PATH": str(ROOT / "skills" / "pptx"),
                "AGENT_WORKSPACE_ROOT": workspace,
                "WORK_IQ_PROJECT_CONNECTION_ID": "/subscriptions/test/connections/work-iq",
            },
            clear=False,
        ), patch.object(generator, "create_harness_agent", side_effect=fake_harness):
            result = generator.create_generator_harness(object())

        self.assertEqual(result, "agent")
        self.assertTrue(captured["disable_web_search"])
        self.assertTrue(captured["disable_tool_auto_approval"])
        self.assertTrue(captured["disable_file_memory"])
        self.assertIsNone(captured["background_agents"])
        self.assertIsNone(captured["shell_executor"])
        self.assertEqual(captured["loop_max_iterations"], 3)

    def test_validator_rejects_paths_outside_session_workspace(self):
        with tempfile.TemporaryDirectory() as workspace, patch.dict(
            os.environ,
            {"AGENT_WORKSPACE_ROOT": workspace},
            clear=False,
        ):
            with self.assertRaises(ValueError):
                validator._workspace_file("..\\outside.pptx")
            with self.assertRaises(ValueError):
                validator._workspace_file("input\\notes.docx")


if __name__ == "__main__":
    unittest.main()
