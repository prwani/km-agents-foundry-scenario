import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentDefinitionTests(unittest.TestCase):
    def test_azure_yaml_has_one_direct_code_hosted_agent(self):
        content = (ROOT / "azure.yaml").read_text(encoding="utf-8")
        self.assertIn("  hosted-case-study-agent:", content)
        self.assertEqual(content.count("host: azure.ai.agent"), 1)
        self.assertEqual(content.count("codeConfiguration:"), 1)
        self.assertIn("azure.ai.agents:", content)
        self.assertIn("project: src", content)
        self.assertIn("entryPoint: main.py", content)
        self.assertNotIn("HOSTED_GENERATOR_A2A_CONNECTION_ID", content)
        self.assertNotIn("HOSTED_VALIDATOR_A2A_CONNECTION_ID", content)

    def test_hosted_direct_code_package_is_self_contained(self):
        service_root = ROOT / "src"
        self.assertTrue((service_root / "main.py").is_file())
        self.assertTrue((service_root / "requirements.txt").is_file())
        self.assertTrue((service_root / ".agentignore").is_file())
        self.assertTrue(
            (service_root / "assets" / "templates" / "contoso-case-study-template.pptx").is_file()
        )
        self.assertTrue(
            (service_root / "assets" / "templates" / "contoso-template-policy.json").is_file()
        )
        self.assertTrue(
            (
                service_root
                / "assets"
                / "templates"
                / "contoso-case-study-template-with-brand-guidelines.pptx"
            ).is_file()
        )
        self.assertTrue((service_root / "skills" / "pptx" / "SKILL.md").is_file())

        mirrored_files = (
            "assets/templates/contoso-case-study-template.pptx",
            "assets/templates/contoso-case-study-template-with-brand-guidelines.pptx",
            "assets/templates/contoso-template-policy.json",
            "skills/pptx/SKILL.md",
        )
        for relative_path in mirrored_files:
            self.assertEqual(
                (ROOT / relative_path).read_bytes(),
                (service_root / relative_path).read_bytes(),
                f"Hosted package copy is stale: {relative_path}",
            )

    def test_three_prompt_agent_definitions_exist(self):
        definitions = sorted((ROOT / "agents" / "prompt").glob("*/agent.yaml"))
        self.assertEqual(len(definitions), 3)
        combined = "\n".join(path.read_text(encoding="utf-8") for path in definitions)
        self.assertEqual(combined.count("kind: prompt"), 3)
        self.assertIn("type: code_interpreter", combined)
        self.assertIn("type: a2a_preview", combined)
        self.assertNotIn("type: work_iq_preview", combined)

    def test_hosted_case_study_agent_uses_harness_with_deterministic_validation(self):
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
        self.assertIn("file_access_disable_readonly_tool_approval=True", content)
        self.assertIn("file_access_disable_write_tool_approval=True", content)
        self.assertIn("skills_paths=", content)
        self.assertIn("extract_uploaded_evidence_tool", content)
        self.assertIn("create_case_study_deck_tool", content)
        self.assertIn("validate_case_study_deck_tool", content)
        self.assertIn("_max_repair_attempts", content)
        self.assertIn("background_agents=None", content)
        self.assertIn("shell_executor=None", content)

    def test_repository_owned_skill_exists_without_restricted_vendor_references(self):
        skill = ROOT / "skills" / "pptx" / "SKILL.md"
        self.assertTrue(skill.is_file())
        restricted_vendor = "anth" + "ropic"
        for path in ROOT.rglob("*"):
            if {".git", ".venv", "__pycache__"} & set(path.parts):
                continue
            if path.is_file() and path.suffix.lower() in {".md", ".py", ".json", ".yaml", ".yml"}:
                self.assertNotIn(restricted_vendor, path.read_text(encoding="utf-8").lower(), str(path))


if __name__ == "__main__":
    unittest.main()
