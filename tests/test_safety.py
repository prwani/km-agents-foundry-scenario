import unittest

from km_agents.contracts import CaseStudyRequest, ImplementationKind, SourceArtifact, SourceFileKind
from km_agents.safety import validate_request


def request_for(summary: str) -> CaseStudyRequest:
    return CaseStudyRequest(
        implementation=ImplementationKind.HOSTED,
        customer_name="Fabrikam",
        customer_name_approved_for_external_use=False,
        opportunity_summary=summary,
        audience="executives",
        template_url="https://contoso.sharepoint.com/sites/km/Templates/template.pptx",
        source_artifacts=(
            SourceArtifact(
                url="https://contoso.sharepoint.com/sites/km/Documents/brief.docx",
                kind=SourceFileKind.DOCX,
                size_bytes=1024,
            ),
        ),
        correlation_id="test-correlation-001",
    )


class SafetyTests(unittest.TestCase):
    def test_safe_request_passes_precheck(self):
        self.assertTrue(validate_request(request_for("Modernize support workflows")).approved)

    def test_sensitive_text_rejects_request(self):
        result = validate_request(request_for("pipeline: $1000000"))
        self.assertFalse(result.approved)
        self.assertTrue(result.findings)

    def test_customer_is_anonymized_without_attestation(self):
        request = request_for("Modernize support workflows")
        self.assertEqual(request.display_customer_name, "Customer")


if __name__ == "__main__":
    unittest.main()
