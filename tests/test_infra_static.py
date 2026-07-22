import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class InfraTests(unittest.TestCase):
    def test_foundry_selected_ip_and_static_egress_are_declared(self):
        content = (ROOT / "infra" / "main.bicep").read_text(encoding="utf-8")
        self.assertIn("publicNetworkAccess: 'Enabled'", content)
        self.assertIn("defaultAction: 'Deny'", content)
        self.assertIn("Microsoft.Network/natGateways", content)
        self.assertIn("publicIPAllocationMethod: 'Static'", content)
        self.assertIn("infrastructureSubnetId", content)
        self.assertIn("workloadProfileType: 'Consumption'", content)
        self.assertIn("Microsoft.Consumption/budgets", content)
        self.assertIn("amount: 50", content)

    def test_bicep_compiles_when_azure_cli_is_available(self):
        az = shutil.which("az.cmd") or shutil.which("az.exe") or shutil.which("az")
        if not az:
            self.skipTest("Azure CLI is not installed")
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    az,
                    "bicep",
                    "build",
                    "--file",
                    str(ROOT / "infra" / "main.bicep"),
                    "--outfile",
                    str(pathlib.Path(temp_dir) / "main.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
