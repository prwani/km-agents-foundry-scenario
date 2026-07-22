import unittest

from km_agents.artifacts import ArtifactNotAvailableError, InMemoryArtifactStore
from km_agents.contracts import SourceFileKind
from km_portal.graph import MicrosoftGraphSourceResolver, SourceRetrievalError


class PortalSecurityTests(unittest.TestCase):
    def test_memory_download_requires_same_user_and_is_not_consumed_by_another_user(self):
        store = InMemoryArtifactStore("test-only-salt")
        reference = store.put(b"PK\x03\x04deck", "case-study.pptx", "owner")

        with self.assertRaises(ArtifactNotAvailableError):
            store.consume(reference.artifact_id, "other-user")

        download = store.consume(reference.artifact_id, "owner")
        self.assertEqual(download.content, b"PK\x03\x04deck")

    def test_source_url_must_be_sharepoint_or_onedrive(self):
        with self.assertRaises(SourceRetrievalError):
            MicrosoftGraphSourceResolver._validate_microsoft_365_url(
                "https://example.com/private.docx"
            )

    def test_source_signature_is_checked_before_agent_upload(self):
        with self.assertRaises(SourceRetrievalError):
            MicrosoftGraphSourceResolver._validate_content_signature(
                b"not-an-office-document", SourceFileKind.DOCX
            )
        with self.assertRaises(SourceRetrievalError):
            MicrosoftGraphSourceResolver._validate_content_signature(
                b"not-a-pdf", SourceFileKind.PDF
            )


if __name__ == "__main__":
    unittest.main()
