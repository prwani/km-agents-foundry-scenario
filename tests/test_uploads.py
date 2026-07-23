import io
import unittest

from fastapi import UploadFile

from km_agents.contracts import SourceFileKind
from km_portal.uploads import (
    MAX_SOURCE_FILE_BYTES,
    UploadValidationError,
    read_uploaded_sources,
)


class UploadValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_supported_office_upload(self):
        sources = await read_uploaded_sources(
            [
                UploadFile(
                    filename="brief.docx",
                    file=io.BytesIO(b"PK\x03\x04valid-office-package"),
                )
            ]
        )
        self.assertEqual(sources[0].name, "brief.docx")
        self.assertEqual(sources[0].kind, SourceFileKind.DOCX)

    async def test_rejects_path_like_filename(self):
        with self.assertRaises(UploadValidationError):
            await read_uploaded_sources(
                [
                    UploadFile(
                        filename="../brief.docx",
                        file=io.BytesIO(b"PK\x03\x04valid-office-package"),
                    )
                ]
            )

    async def test_rejects_upload_over_file_limit(self):
        with self.assertRaises(UploadValidationError):
            await read_uploaded_sources(
                [
                    UploadFile(
                        filename="oversized.docx",
                        file=io.BytesIO(b"PK\x03\x04" + b"x" * MAX_SOURCE_FILE_BYTES),
                    )
                ]
            )


if __name__ == "__main__":
    unittest.main()
