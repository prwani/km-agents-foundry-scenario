import unittest

from fastapi.testclient import TestClient

from km_agents.artifacts import InMemoryArtifactStore
from km_agents.contracts import (
    CaseStudyRequest,
    CaseStudyResponse,
    ImplementationKind,
    ValidationResult,
)
from km_portal.authentication import AuthenticatedUser, AuthenticationError
from km_portal.gateway import (
    GatewayConfigurationError,
    GatewayExecution,
)
from km_portal.graph import RetrievedSource
from km_portal.main import PortalServices, app, set_portal_services


class FakeAuthenticator:
    def authenticate(self, authorization: str | None) -> AuthenticatedUser:
        if authorization != "Bearer synthetic-token":
            raise AuthenticationError("invalid token")
        return AuthenticatedUser(
            subject="synthetic-user",
            tenant_id="synthetic-tenant",
            access_token="synthetic-token",
        )


class FakeSourceResolver:
    def retrieve_template(self, user: AuthenticatedUser, template_url: str) -> RetrievedSource:
        return RetrievedSource(
            name="template.pptx",
            kind="pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            content=b"PK\x03\x04template",
            source_url=template_url,
        )

    def retrieve(self, user: AuthenticatedUser, artifact: object) -> RetrievedSource:
        return RetrievedSource(
            name="brief.docx",
            kind="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=b"PK\x03\x04source",
            source_url="https://contoso.sharepoint.com/sites/km/Documents/brief.docx",
        )


class FakeGateway:
    def invoke(
        self, request: CaseStudyRequest, sources: tuple[RetrievedSource, ...]
    ) -> GatewayExecution:
        response = CaseStudyResponse(
            implementation=request.implementation,
            correlation_id=request.correlation_id,
            status="approved",
            validation=ValidationResult.approved_result(),
        )
        return GatewayExecution(
            response=response,
            artifact_name="case-study.pptx",
            artifact_content=b"PK\x03\x04generated-deck",
        )


class RejectedGateway:
    def invoke(
        self, request: CaseStudyRequest, sources: tuple[RetrievedSource, ...]
    ) -> GatewayExecution:
        return GatewayExecution(
            response=CaseStudyResponse(
                implementation=request.implementation,
                correlation_id=request.correlation_id,
                status="rejected",
                validation=ValidationResult.rejected("Synthetic policy test"),
            )
        )


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
                    "size_bytes": 1024,
                }
            ],
            "correlation_id": "portal-test-001",
        }
        set_portal_services(
            PortalServices(
                authenticator=FakeAuthenticator(),
                source_resolver=FakeSourceResolver(),
                artifact_store=InMemoryArtifactStore("test-only-salt"),
                gateway_factory=lambda _: FakeGateway(),
            )
        )

    def tearDown(self):
        set_portal_services(None)

    def test_capabilities_expose_both_implementations(self):
        response = self.client.get("/api/capabilities")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["implementations"], ["prompt", "hosted"])
        self.assertEqual(response.json()["download_ttl_seconds"], 900)

    def test_submission_requires_bearer_authentication(self):
        response = self.client.post("/api/case-studies", json=self.payload)
        self.assertEqual(response.status_code, 401)

    def test_submission_rejects_unverified_bearer_token(self):
        response = self.client.post(
            "/api/case-studies",
            json=self.payload,
            headers={"Authorization": "Bearer invalid"},
        )
        self.assertEqual(response.status_code, 401)

    def test_submission_creates_single_use_authenticated_download(self):
        response = self.client.post(
            "/api/case-studies",
            json=self.payload,
            headers={"Authorization": "Bearer synthetic-token"},
        )
        self.assertEqual(response.status_code, 200)
        artifact_id = response.json()["artifact"]["artifact_id"]

        download = self.client.get(
            f"/api/downloads/{artifact_id}",
            headers={"Authorization": "Bearer synthetic-token"},
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"PK\x03\x04generated-deck")
        self.assertEqual(download.headers["cache-control"], "no-store")

        repeated_download = self.client.get(
            f"/api/downloads/{artifact_id}",
            headers={"Authorization": "Bearer synthetic-token"},
        )
        self.assertEqual(repeated_download.status_code, 404)

    def test_rejected_validation_never_creates_download(self):
        set_portal_services(
            PortalServices(
                authenticator=FakeAuthenticator(),
                source_resolver=FakeSourceResolver(),
                artifact_store=InMemoryArtifactStore("test-only-salt"),
                gateway_factory=lambda _: RejectedGateway(),
            )
        )
        response = self.client.post(
            "/api/case-studies",
            json=self.payload,
            headers={"Authorization": "Bearer synthetic-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["validation"]["approved"])
        self.assertIsNone(response.json()["artifact"])

    def test_gateway_configuration_failure_is_explicit(self):
        set_portal_services(
            PortalServices(
                authenticator=FakeAuthenticator(),
                source_resolver=FakeSourceResolver(),
                artifact_store=InMemoryArtifactStore("test-only-salt"),
                gateway_factory=lambda _: (_ for _ in ()).throw(
                    GatewayConfigurationError("missing endpoint")
                ),
            )
        )
        response = self.client.post(
            "/api/case-studies",
            json=self.payload,
            headers={"Authorization": "Bearer synthetic-token"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
