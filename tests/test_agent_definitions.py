import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentDefinitionTests(unittest.TestCase):
    def test_azure_yaml_has_three_direct_code_hosted_agents(self):
        content = (ROOT / "azure.yaml").read_text(encoding="utf-8")
        for service in (
            "hosted-orchestrator",
            "hosted-case-study-generator",
            "hosted-validator",
        ):
            self.assertIn(f"  {service}:", content)
        self.assertEqual(content.count("host: azure.ai.agent"), 3)
        self.assertEqual(content.count("codeConfiguration:"), 3)

    def test_three_prompt_agent_definitions_exist(self):
        definitions = sorted((ROOT / "agents" / "prompt").glob("*/agent.yaml"))
        self.assertEqual(len(definitions), 3)
        combined = "\n".join(path.read_text(encoding="utf-8") for path in definitions)
        self.assertEqual(combined.count("kind: prompt"), 3)
        self.assertIn("type: code_interpreter", combined)
        self.assertIn("type: a2a_preview", combined)
        self.assertIn("type: work_iq_preview", combined)

    def test_hosted_generator_uses_harness_with_unsafe_defaults_disabled(self):
        content = (
            ROOT
            / "src"
            / "km_agents"
            / "agents"
            / "hosted"
            / "case_study_generator"
            / "main.py"
        ).read_text(encoding="utf-8")
        self.assertIn("create_harness_agent", content)
        self.assertIn("disable_web_search=True", content)
        self.assertIn("disable_tool_auto_approval=True", content)
        self.assertIn("skills_paths=", content)
        self.assertIn("background_agents=None", content)
        self.assertIn("shell_executor=None", content)

    def test_repository_owned_skill_exists_without_restricted_vendor_references(self):
        skill = ROOT / "skills" / "pptx" / "SKILL.md"
        self.assertTrue(skill.is_file())
        restricted_vendor = "anth" + "ropic"
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".py", ".json", ".yaml", ".yml"}:
                self.assertNotIn(restricted_vendor, path.read_text(encoding="utf-8").lower(), str(path))


if __name__ == "__main__":
    unittest.main()
