import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

from azure.ai.projects.models import A2APreviewTool, CodeInterpreterTool, WorkIQPreviewTool


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "provision_prompt_agents.py"
SPEC = importlib.util.spec_from_file_location("provision_prompt_agents", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PromptProvisioningTests(unittest.TestCase):
    def test_all_definitions_load_in_specialist_first_order(self):
        specs = [MODULE.load_spec(folder, resolve=False) for folder in MODULE.DEPLOYMENT_ORDER]
        self.assertEqual(
            [spec.name for spec in specs],
            ["km-prompt-case-study-generator", "km-prompt-validator", "km-prompt-orchestrator"],
        )
        self.assertTrue(all(spec.instructions for spec in specs))

    def test_generator_builds_code_interpreter_and_work_iq_tools(self):
        spec = MODULE.load_spec("case-study-generator", resolve=False)
        with patch.dict(
            "os.environ",
            {"WORK_IQ_PROJECT_CONNECTION_ID": "/subscriptions/test/connections/work-iq"},
            clear=False,
        ):
            tools = MODULE.build_tools(spec)
        self.assertIsInstance(tools[0], CodeInterpreterTool)
        self.assertIsInstance(tools[1], WorkIQPreviewTool)

    def test_orchestrator_builds_two_a2a_tools(self):
        spec = MODULE.load_spec("orchestrator", resolve=False)
        with patch.dict(
            "os.environ",
            {
                "PROMPT_GENERATOR_A2A_CONNECTION_ID": "/subscriptions/test/connections/generator",
                "PROMPT_VALIDATOR_A2A_CONNECTION_ID": "/subscriptions/test/connections/validator",
            },
            clear=False,
        ):
            tools = MODULE.build_tools(spec)
        self.assertEqual(len(tools), 2)
        self.assertTrue(all(isinstance(tool, A2APreviewTool) for tool in tools))

    def test_missing_connection_fails_explicitly(self):
        spec = MODULE.load_spec("case-study-generator", resolve=False)
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "WORK_IQ_PROJECT_CONNECTION_ID"):
                MODULE.build_tools(spec)


if __name__ == "__main__":
    unittest.main()
