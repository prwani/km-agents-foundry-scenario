import json
import unittest

from fastapi.testclient import TestClient

from km_agents.artifacts import InMemoryArtifactStore
from km_agents.contracts import (
    CaseStudyRequest,
    CaseStudyResponse,
    ValidationResult,
)
from km_portal.authentication import AuthenticatedUser, AuthenticationError
from km_portal.gateway import GatewayConfigurationError, GatewayExecution
from km_portal.main import PortalServices, app, set_portal_services


VALID_AUTHORIZATION = "Bearer valid-token"


class FakeAuthenticator:
    def authenticate(self, authorization: str | None) -> AuthenticatedUser:
        if authorization != VALID_AUTHORIZATION:
            raise AuthenticationError("invalid token")
        return AuthenticatedUser(
            subject="synthetic-user",
            tenant_id="synthetic-tenant",
            access_token="synthetic-token",
        )


class FakeGateway:
    def invoke(
        self, request: CaseStudyRequest, sources: tuple[object, ...]
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
        self, request: CaseStudyRequest, sources: tuple[object, ...]
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
            "correlation_id": "portal-test-001",
        }
        set_portal_services(
            PortalServices(
                authenticator=FakeAuthenticator(),
                artifact_store=InMemoryArtifactStore("test-only-salt"),
                gateway_factory=lambda _, __: FakeGateway(),
            )
        )

    def tearDown(self):
        set_portal_services(None)

    def test_capabilities_expose_direct_upload_limits(self):
        response = self.client.get("/api/capabilities")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["implementations"], ["prompt", "hosted"])
        self.assertEqual(response.json()["max_source_files"], 10)
        self.assertEqual(response.json()["download_ttl_seconds"], 900)

    def test_submission_requires_bearer_authentication(self):
        response = self._submit()
        self.assertEqual(response.status_code, 401)

    def test_submission_rejects_unverified_bearer_token(self):
        response = self._submit(headers={"Authorization": "Bearer invalid-token"})
        self.assertEqual(response.status_code, 401)

    def test_submission_creates_single_use_authenticated_download(self):
        response = self._submit(headers={"Authorization": VALID_AUTHORIZATION})
        self.assertEqual(response.status_code, 200)
        artifact_id = response.json()["artifact"]["artifact_id"]

        download = self.client.get(
            f"/api/downloads/{artifact_id}",
            headers={"Authorization": VALID_AUTHORIZATION},
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"PK\x03\x04generated-deck")
        self.assertEqual(download.headers["cache-control"], "no-store")

        repeated_download = self.client.get(
            f"/api/downloads/{artifact_id}",
            headers={"Authorization": VALID_AUTHORIZATION},
        )
        self.assertEqual(repeated_download.status_code, 404)

    def test_invalid_upload_is_rejected_before_gateway_invocation(self):
        response = self._submit(
            content=b"not-an-office-document",
            headers={"Authorization": VALID_AUTHORIZATION},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejected_validation_never_creates_download(self):
        set_portal_services(
            PortalServices(
                authenticator=FakeAuthenticator(),
                artifact_store=InMemoryArtifactStore("test-only-salt"),
                gateway_factory=lambda _, __: RejectedGateway(),
            )
        )
        response = self._submit(headers={"Authorization": VALID_AUTHORIZATION})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["validation"]["approved"])
        self.assertIsNone(response.json()["artifact"])

    def test_gateway_configuration_failure_is_explicit(self):
        set_portal_services(
            PortalServices(
                authenticator=FakeAuthenticator(),
                artifact_store=InMemoryArtifactStore("test-only-salt"),
                gateway_factory=lambda _, __: (_ for _ in ()).throw(
                    GatewayConfigurationError("missing endpoint")
                ),
            )
        )
        response = self._submit(headers={"Authorization": VALID_AUTHORIZATION})
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"])

    def _submit(
        self,
        *,
        content: bytes = b"PK\x03\x04source",
        headers: dict[str, str] | None = None,
    ):
        return self.client.post(
            "/api/case-studies",
            data={"request_json": json.dumps(self.payload)},
            files={
                "source_files": (
                    "brief.docx",
                    content,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers=headers,
        )


if __name__ == "__main__":
    unittest.main()
