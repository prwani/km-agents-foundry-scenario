import unittest

from km_portal.gateway import _presentation_file_references


class PromptGatewayTests(unittest.TestCase):
    def test_reads_only_powerpoint_container_file_citations(self):
        response = {
            "output": [
                {
                    "content": [
                        {
                            "annotations": [
                                {
                                    "type": "container_file_citation",
                                    "container_id": "container-1",
                                    "file_id": "file-deck",
                                    "filename": "case-study.pptx",
                                },
                                {
                                    "type": "container_file_citation",
                                    "container_id": "container-1",
                                    "file_id": "file-chart",
                                    "filename": "chart.png",
                                },
                            ]
                        }
                    ]
                }
            ]
        }

        references = _presentation_file_references(response)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].container_id, "container-1")
        self.assertEqual(references[0].file_id, "file-deck")
        self.assertEqual(references[0].filename, "case-study.pptx")


if __name__ == "__main__":
    unittest.main()
