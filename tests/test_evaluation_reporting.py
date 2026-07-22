import json
import unittest
from pathlib import Path

from km_agents.evaluation import EvaluationDataError, RunRecord, generate_report


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "evaluation" / "corpus" / "v1" / "manifest.json").read_text(encoding="utf-8")
)


def record_for(case: dict, implementation: str, repetition: int) -> RunRecord:
    expected = case["expected"]
    rejected = expected["must_fail_closed"]
    return RunRecord.from_json(
        {
            "case_id": case["id"],
            "implementation": implementation,
            "repetition": repetition,
            "status": "rejected" if rejected else "approved",
            "artifact_delivered": not rejected,
            "valid_pptx": not rejected,
            "template_compliant": True,
            "sensitive_information_revealed": False,
            "customer_name_compliant": True,
            "validation_conclusive": True,
            "temporary_artifacts_cleaned": True,
            "observed_customer_display_name": expected["expected_customer_display_name"],
            "uncertainty_finding_present": expected["requires_uncertainty_finding"],
            "latency_ms": 1000 + repetition,
            "estimated_cost_usd": 0.01,
            "human_correction_minutes": 0,
            "repair_attempts": 0,
            "content_quality_score": None if rejected else 90,
            "failure_categories": [],
        }
    )


class EvaluationReportingTests(unittest.TestCase):
    def test_complete_synthetic_matrix_is_scored(self):
        records = [
            record_for(case, implementation, repetition)
            for case in MANIFEST["cases"]
            for implementation in MANIFEST["implementations"]
            for repetition in range(1, MANIFEST["repetitions_per_stack"] + 1)
        ]

        report = generate_report(MANIFEST, records)

        self.assertEqual(report["observed_run_count"], 72)
        self.assertTrue(report["stacks"]["prompt"]["hard_gate_eligible"])
        self.assertTrue(report["stacks"]["hosted"]["hard_gate_eligible"])
        self.assertEqual(report["stacks"]["prompt"]["success_rate"], 1.0)
        self.assertIsNotNone(report["stacks"]["prompt"]["weighted_score"])

    def test_missing_matrix_entry_fails_explicitly(self):
        records = [
            record_for(case, implementation, repetition)
            for case in MANIFEST["cases"]
            for implementation in MANIFEST["implementations"]
            for repetition in range(1, MANIFEST["repetitions_per_stack"] + 1)
        ][1:]

        with self.assertRaisesRegex(EvaluationDataError, "incomplete"):
            generate_report(MANIFEST, records)

    def test_hard_gate_failure_disqualifies_only_affected_stack(self):
        records = [
            record_for(case, implementation, repetition)
            for case in MANIFEST["cases"]
            for implementation in MANIFEST["implementations"]
            for repetition in range(1, MANIFEST["repetitions_per_stack"] + 1)
        ]
        compromised = records[0]
        records[0] = RunRecord.from_json(
            {
                **compromised.__dict__,
                "sensitive_information_revealed": True,
                "failure_categories": ["sensitive_information"],
            }
        )

        report = generate_report(MANIFEST, records)

        self.assertFalse(report["stacks"]["prompt"]["hard_gate_eligible"])
        self.assertIsNone(report["stacks"]["prompt"]["weighted_score"])
        self.assertTrue(report["stacks"]["hosted"]["hard_gate_eligible"])


if __name__ == "__main__":
    unittest.main()
