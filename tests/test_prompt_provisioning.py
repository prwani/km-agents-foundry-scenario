import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

from azure.ai.projects.models import A2APreviewTool, CodeInterpreterTool


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

    def test_generator_builds_code_interpreter_with_canonical_template_support(self):
        spec = MODULE.load_spec("case-study-generator", resolve=False)
        tools = MODULE.build_tools(spec, code_interpreter_file_ids=("file-template",))
        self.assertEqual(len(tools), 1)
        self.assertIsInstance(tools[0], CodeInterpreterTool)
        self.assertEqual(tools[0].container.file_ids, ["file-template"])
        self.assertIn("source filenames", spec.instructions)
        self.assertIn("Not provided in source evidence", spec.instructions)
        self.assertIn("create no PPTX", spec.instructions)
        self.assertIn("final Code Interpreter", spec.instructions)
        self.assertIn("single PDF", spec.instructions)

    def test_validator_builds_code_interpreter_with_template_and_policy_support(self):
        spec = MODULE.load_spec("validator", resolve=False)
        tools = MODULE.build_tools(
            spec, code_interpreter_file_ids=("file-template", "file-policy")
        )
        self.assertEqual(tools[0].container.file_ids, ["file-template", "file-policy"])
        self.assertIn(
            "Informational findings alone do not reject a deck.", spec.instructions
        )
        self.assertIn("validation policy fingerprints as authoritative", spec.instructions)
        self.assertIn("editable_shapes", spec.instructions)
        self.assertIn("empty findings array must always produce `approved: true`", spec.instructions)

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

    def test_generator_does_not_require_a_work_iq_connection(self):
        spec = MODULE.load_spec("case-study-generator", resolve=False)
        with patch.dict("os.environ", {}, clear=True):
            tools = MODULE.build_tools(spec)
        self.assertEqual(len(tools), 1)


if __name__ == "__main__":
    unittest.main()
