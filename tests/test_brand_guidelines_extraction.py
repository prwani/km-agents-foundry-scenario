import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import extract_brand_guidelines as extractor  # noqa: E402


class BrandGuidelinesExtractionTests(unittest.TestCase):
    def test_committed_markdown_matches_current_brand_deck(self):
        """Guards against editing the markdown by hand or forgetting to regenerate it."""
        markdown = extractor.extract_markdown(extractor.DEFAULT_SOURCE)
        for output in extractor.DEFAULT_OUTPUTS:
            self.assertTrue(output.is_file(), f"Missing generated brand-guidelines file: {output}")
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                markdown,
                f"{output} is stale; run 'python scripts/extract_brand_guidelines.py' to regenerate it.",
            )

    def test_check_mode_detects_drift(self):
        import hashlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            stale_output = pathlib.Path(tmp) / "brand-guidelines.md"
            stale_output.write_text(
                "<!-- source_sha256: 0000000000000000000000000000000000000000000000000000000000000000 -->\n",
                encoding="utf-8",
            )
            committed_hash = extractor._extract_committed_hash(stale_output)
            actual_hash = hashlib.sha256(extractor.DEFAULT_SOURCE.read_bytes()).hexdigest()
            self.assertNotEqual(committed_hash, actual_hash)

    def test_extraction_excludes_canonical_case_study_slides(self):
        markdown = extractor.extract_markdown(extractor.DEFAULT_SOURCE)
        self.assertNotIn("Slide 1:", markdown)
        self.assertNotIn("Slide 8:", markdown)
        self.assertIn("Slide 9:", markdown)
        self.assertIn("BRAND PROMISE", markdown)


if __name__ == "__main__":
    unittest.main()
