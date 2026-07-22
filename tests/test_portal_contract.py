import unittest

from fastapi.testclient import TestClient

from km_portal.main import app


class PortalContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = {
            "implementation": "prompt",
            "customer_name": "Fabrikam",
            "customer_name_approved_for_external_use": False,
            "opportunity_summary": "Modernize support workflows",
            "audience": "executives",
            "template_url": "https://contoso.sharepoint.com/sites/km/Templates/template.pptx",
            "source_artifacts": [
                {
                    "url": "https://contoso.sharepoint.com/sites/km/Documents/brief.docx",
                    "kind": "docx",
                    "size_bytes": 1024
                }
            ],
            "correlation_id": "portal-test-001"
        }

    def test_capabilities_expose_both_implementations(self):
        response = self.client.get("/api/capabilities")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["implementations"], ["prompt", "hosted"])
        self.assertEqual(response.json()["download_ttl_seconds"], 900)

    def test_submission_requires_authentication(self):
        response = self.client.post("/api/case-studies", json=self.payload)
        self.assertEqual(response.status_code, 401)

    def test_configured_gateway_is_required(self):
        response = self.client.post(
            "/api/case-studies",
            json=self.payload,
            headers={"X-MS-CLIENT-PRINCIPAL-ID": "synthetic-user"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("prompt Foundry orchestration gateway is not configured", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
