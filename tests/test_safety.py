import unittest

from km_agents.contracts import CaseStudyRequest, ImplementationKind
from km_agents.safety import validate_request


def request_for(summary: str) -> CaseStudyRequest:
    return CaseStudyRequest(
        implementation=ImplementationKind.HOSTED,
        customer_name="Fabrikam",
        customer_name_approved_for_external_use=False,
        opportunity_summary=summary,
        audience="executives",
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
