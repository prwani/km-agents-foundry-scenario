import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from km_agents.config import ConfigurationError
from km_agents.agents.hosted.case_study_generator import main as generator
from km_agents.agents.hosted.case_study_generator import validation


ROOT = pathlib.Path(__file__).resolve().parents[1]


class HostedAgentTests(unittest.TestCase):
    def test_hosted_case_study_harness_is_scoped_and_uses_deterministic_validation(self):
        captured = {}

        def fake_harness(**kwargs):
            captured.update(kwargs)
            return "agent"

        with tempfile.TemporaryDirectory() as workspace, patch.dict(
            os.environ,
            {
                "PPTX_SKILL_PATH": str(ROOT / "skills" / "pptx"),
                "CASE_STUDY_TEMPLATE_PATH": str(
                    ROOT / "assets" / "templates" / "contoso-case-study-template.pptx"
                ),
                "AGENT_WORKSPACE_ROOT": workspace,
            },
            clear=False,
        ), patch.object(generator, "create_harness_agent", side_effect=fake_harness):
            result = generator.create_generator_harness(object())

        self.assertEqual(result, "agent")
        self.assertTrue(captured["disable_web_search"])
        self.assertTrue(captured["disable_tool_auto_approval"])
        self.assertTrue(captured["disable_file_memory"])
        self.assertTrue(captured["file_access_disable_readonly_tool_approval"])
        self.assertTrue(captured["file_access_disable_write_tool_approval"])
        self.assertIsNone(captured["background_agents"])
        self.assertIsNone(captured["shell_executor"])
        self.assertEqual(captured["loop_max_iterations"], 3)
        self.assertEqual(len(captured["tools"]), 3)
        self.assertIn("extract_uploaded_evidence", str(captured["tools"][0]))
        self.assertIn("generate_case_study_deck", str(captured["tools"][1]))
        self.assertIn("validate_case_study_deck", str(captured["tools"][2]))
        generation_schema = captured["tools"][1].input_model.model_json_schema()
        self.assertIn("architecture_components", str(generation_schema))
        self.assertIn("measurable_outcomes", str(generation_schema))
        self.assertFalse(captured["history_provider"].load_messages)
        self.assertNotIn("default_options", captured)

    def test_hosted_case_study_agent_requires_exact_repair_limit(self):
        with patch.dict(os.environ, {"MAX_REPAIR_ATTEMPTS": "3"}, clear=False):
            with self.assertRaises(ConfigurationError):
                generator._max_repair_attempts()

    def test_validation_rejects_paths_outside_session_workspace(self):
        with tempfile.TemporaryDirectory() as workspace, patch.dict(
            os.environ,
            {"AGENT_WORKSPACE_ROOT": workspace},
            clear=False,
        ):
            with self.assertRaises(ValueError):
                validation.workspace_deck_path("..\\outside.pptx")
            with self.assertRaises(ValueError):
                validation.workspace_deck_path("input\\notes.docx")


if __name__ == "__main__":
    unittest.main()
