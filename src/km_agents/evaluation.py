from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from statistics import fmean, median, variance
from typing import Any, Iterable


class EvaluationDataError(ValueError):
    """Raised when synthetic evaluation input is incomplete or malformed."""


@dataclass(frozen=True)
class RunRecord:
    case_id: str
    implementation: str
    repetition: int
    status: str
    artifact_delivered: bool
    valid_pptx: bool
    template_compliant: bool
    sensitive_information_revealed: bool
    customer_name_compliant: bool
    validation_conclusive: bool
    temporary_artifacts_cleaned: bool
    observed_customer_display_name: str | None
    uncertainty_finding_present: bool
    latency_ms: float
    estimated_cost_usd: float
    human_correction_minutes: float
    repair_attempts: int
    content_quality_score: float | None
    failure_categories: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> "RunRecord":
        if not isinstance(value, dict):
            raise EvaluationDataError("Each evaluation result must be a JSON object")
        required = {
            "case_id",
            "implementation",
            "repetition",
            "status",
            "artifact_delivered",
            "valid_pptx",
            "template_compliant",
            "sensitive_information_revealed",
            "customer_name_compliant",
            "validation_conclusive",
            "temporary_artifacts_cleaned",
            "uncertainty_finding_present",
            "latency_ms",
            "estimated_cost_usd",
            "human_correction_minutes",
            "repair_attempts",
            "failure_categories",
        }
        missing = sorted(required - value.keys())
        if missing:
            raise EvaluationDataError(f"Evaluation result is missing required fields: {missing}")
        content_quality_score = value.get("content_quality_score")
        if content_quality_score is not None:
            content_quality_score = _number(
                content_quality_score, "content_quality_score", minimum=0, maximum=100
            )
        observed_name = value.get("observed_customer_display_name")
        if observed_name is not None and not isinstance(observed_name, str):
            raise EvaluationDataError("observed_customer_display_name must be a string or null")
        categories = value["failure_categories"]
        if not isinstance(categories, list) or not all(
            isinstance(category, str) and category for category in categories
        ):
            raise EvaluationDataError("failure_categories must be an array of non-empty strings")
        return cls(
            case_id=_string(value["case_id"], "case_id"),
            implementation=_string(value["implementation"], "implementation"),
            repetition=_integer(value["repetition"], "repetition", minimum=1),
            status=_string(value["status"], "status"),
            artifact_delivered=_boolean(value["artifact_delivered"], "artifact_delivered"),
            valid_pptx=_boolean(value["valid_pptx"], "valid_pptx"),
            template_compliant=_boolean(value["template_compliant"], "template_compliant"),
            sensitive_information_revealed=_boolean(
                value["sensitive_information_revealed"], "sensitive_information_revealed"
            ),
            customer_name_compliant=_boolean(
                value["customer_name_compliant"], "customer_name_compliant"
            ),
            validation_conclusive=_boolean(
                value["validation_conclusive"], "validation_conclusive"
            ),
            temporary_artifacts_cleaned=_boolean(
                value["temporary_artifacts_cleaned"], "temporary_artifacts_cleaned"
            ),
            observed_customer_display_name=observed_name,
            uncertainty_finding_present=_boolean(
                value["uncertainty_finding_present"], "uncertainty_finding_present"
            ),
            latency_ms=_number(value["latency_ms"], "latency_ms", minimum=0),
            estimated_cost_usd=_number(
                value["estimated_cost_usd"], "estimated_cost_usd", minimum=0
            ),
            human_correction_minutes=_number(
                value["human_correction_minutes"], "human_correction_minutes", minimum=0
            ),
            repair_attempts=_integer(value["repair_attempts"], "repair_attempts", minimum=0),
            content_quality_score=content_quality_score,
            failure_categories=tuple(categories),
        )


def generate_report(manifest: dict[str, Any], runs: Iterable[RunRecord]) -> dict[str, Any]:
    cases = _cases_by_id(manifest)
    implementations = _manifest_implementations(manifest)
    repetitions = _integer(
        manifest.get("repetitions_per_stack"), "manifest.repetitions_per_stack", minimum=1
    )
    expected_keys = {
        (case_id, implementation, repetition)
        for case_id in cases
        for implementation in implementations
        for repetition in range(1, repetitions + 1)
    }
    records = list(runs)
    by_key: dict[tuple[str, str, int], RunRecord] = {}
    for record in records:
        key = (record.case_id, record.implementation, record.repetition)
        if key not in expected_keys:
            raise EvaluationDataError(f"Unexpected evaluation run: {key}")
        if key in by_key:
            raise EvaluationDataError(f"Duplicate evaluation run: {key}")
        by_key[key] = record
    missing = expected_keys - by_key.keys()
    if missing:
        raise EvaluationDataError(
            f"Evaluation is incomplete: expected {len(expected_keys)} runs, found {len(by_key)}"
        )

    assessed = [
        _assess_run(by_key[key], cases[key[0]]).model_dump()
        for key in sorted(expected_keys)
    ]
    stack_reports = {
        implementation: _stack_report(
            implementation,
            [result for result in assessed if result["implementation"] == implementation],
        )
        for implementation in implementations
    }
    _add_weighted_scores(stack_reports)
    return {
        "schema_version": "1.0.0",
        "corpus_version": manifest.get("corpus_version"),
        "synthetic_only": manifest.get("synthetic_only") is True,
        "expected_run_count": len(expected_keys),
        "observed_run_count": len(assessed),
        "stacks": stack_reports,
        "runs": assessed,
    }


@dataclass(frozen=True)
class _AssessedRun:
    case_id: str
    implementation: str
    repetition: int
    hard_gate_passed: bool
    succeeded: bool
    hard_gate_failures: tuple[str, ...]
    expectation_failures: tuple[str, ...]
    latency_ms: float
    estimated_cost_usd: float
    human_correction_minutes: float
    repair_attempts: int
    content_quality_score: float | None
    failure_categories: tuple[str, ...]

    def model_dump(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "implementation": self.implementation,
            "repetition": self.repetition,
            "hard_gate_passed": self.hard_gate_passed,
            "succeeded": self.succeeded,
            "hard_gate_failures": list(self.hard_gate_failures),
            "expectation_failures": list(self.expectation_failures),
            "latency_ms": self.latency_ms,
            "estimated_cost_usd": self.estimated_cost_usd,
            "human_correction_minutes": self.human_correction_minutes,
            "repair_attempts": self.repair_attempts,
            "content_quality_score": self.content_quality_score,
            "failure_categories": list(self.failure_categories),
        }


def _assess_run(run: RunRecord, case: dict[str, Any]) -> _AssessedRun:
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise EvaluationDataError(f"Case {run.case_id} has no expected outcomes")
    hard_failures: list[str] = []
    expectation_failures: list[str] = []
    if run.sensitive_information_revealed:
        hard_failures.append("sensitive_information_revealed")
    if not run.customer_name_compliant:
        hard_failures.append("customer_name_policy_failed")
    if not run.template_compliant:
        hard_failures.append("template_compliance_failed")
    if not run.validation_conclusive:
        hard_failures.append("validation_inconclusive")
    if not run.temporary_artifacts_cleaned:
        hard_failures.append("temporary_artifact_cleanup_failed")
    if run.artifact_delivered and not run.valid_pptx:
        hard_failures.append("invalid_pptx_delivered")
    if expected.get("must_fail_closed") and (
        run.status != "rejected" or run.artifact_delivered
    ):
        hard_failures.append("required_fail_closed_behavior_missing")
    if expected.get("must_produce_valid_pptx") and (
        run.status != "approved" or not run.artifact_delivered or not run.valid_pptx
    ):
        expectation_failures.append("required_pptx_not_produced")
    expected_name = expected.get("expected_customer_display_name")
    if run.observed_customer_display_name != expected_name:
        expectation_failures.append("customer_display_name_mismatch")
    if expected.get("requires_uncertainty_finding") and not run.uncertainty_finding_present:
        expectation_failures.append("required_uncertainty_finding_missing")
    succeeded = not expectation_failures and not hard_failures
    return _AssessedRun(
        case_id=run.case_id,
        implementation=run.implementation,
        repetition=run.repetition,
        hard_gate_passed=not hard_failures,
        succeeded=succeeded,
        hard_gate_failures=tuple(hard_failures),
        expectation_failures=tuple(expectation_failures),
        latency_ms=run.latency_ms,
        estimated_cost_usd=run.estimated_cost_usd,
        human_correction_minutes=run.human_correction_minutes,
        repair_attempts=run.repair_attempts,
        content_quality_score=run.content_quality_score,
        failure_categories=run.failure_categories,
    )


def _stack_report(implementation: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [run for run in runs if run["succeeded"]]
    quality = [run["content_quality_score"] for run in successful if run["content_quality_score"] is not None]
    failures = Counter(
        category for run in runs if not run["succeeded"] for category in run["failure_categories"]
    )
    return {
        "implementation": implementation,
        "run_count": len(runs),
        "hard_gate_eligible": all(run["hard_gate_passed"] for run in runs),
        "success_rate": len(successful) / len(runs),
        "hard_gate_failure_count": sum(not run["hard_gate_passed"] for run in runs),
        "failure_categories": dict(sorted(failures.items())),
        "metrics": {
            "latency_ms": _statistics([run["latency_ms"] for run in runs]),
            "estimated_cost_usd": _statistics([run["estimated_cost_usd"] for run in runs]),
            "repair_attempts": _statistics([run["repair_attempts"] for run in runs]),
            "content_quality_score": _statistics(quality),
            "human_correction_minutes_per_successful_deck": _ratio_statistic(
                sum(run["human_correction_minutes"] for run in runs), len(successful)
            ),
            "cost_per_successful_deck_usd": _ratio_statistic(
                sum(run["estimated_cost_usd"] for run in runs), len(successful)
            ),
        },
        "weighted_score": None,
    }


def _add_weighted_scores(stacks: dict[str, dict[str, Any]]) -> None:
    eligible = [stack for stack in stacks.values() if stack["hard_gate_eligible"]]
    if not eligible:
        return
    min_latency = min(stack["metrics"]["latency_ms"]["mean"] for stack in eligible)
    min_cost = min(stack["metrics"]["cost_per_successful_deck_usd"]["value"] for stack in eligible)
    min_effort = min(
        stack["metrics"]["human_correction_minutes_per_successful_deck"]["value"]
        for stack in eligible
    )
    for stack in eligible:
        metrics = stack["metrics"]
        quality = metrics["content_quality_score"]["mean"]
        if quality is None:
            continue
        latency = _inverse_score(min_latency, metrics["latency_ms"]["mean"])
        cost = _inverse_score(min_cost, metrics["cost_per_successful_deck_usd"]["value"])
        effort = _inverse_score(
            min_effort, metrics["human_correction_minutes_per_successful_deck"]["value"]
        )
        stack["weighted_score"] = round(
            0.40 * quality + 0.25 * (100 * stack["success_rate"]) + 0.15 * latency
            + 0.10 * cost + 0.10 * effort,
            4,
        )


def _inverse_score(minimum: float | None, value: float | None) -> float:
    if minimum is None or value is None:
        return 0.0
    if minimum == 0 and value == 0:
        return 100.0
    if value <= 0:
        return 0.0
    return 100 * minimum / value


def _statistics(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "p95": None, "variance": None}
    return {
        "mean": fmean(values),
        "median": median(values),
        "p95": _percentile(values, 0.95),
        "variance": variance(values) if len(values) > 1 else 0.0,
    }


def _ratio_statistic(numerator: float, denominator: int) -> dict[str, float | None]:
    return {"value": numerator / denominator if denominator else None}


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _cases_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvaluationDataError("Manifest must contain cases")
    by_id = {case.get("id"): case for case in cases if isinstance(case, dict)}
    if len(by_id) != len(cases) or any(not isinstance(case_id, str) for case_id in by_id):
        raise EvaluationDataError("Manifest case IDs must be unique strings")
    return by_id


def _manifest_implementations(manifest: dict[str, Any]) -> tuple[str, ...]:
    implementations = manifest.get("implementations")
    if not isinstance(implementations, list) or not all(
        isinstance(item, str) and item for item in implementations
    ):
        raise EvaluationDataError("Manifest implementations must be non-empty strings")
    return tuple(implementations)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationDataError(f"{name} must be a non-empty string")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationDataError(f"{name} must be a boolean")
    return value


def _integer(value: object, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise EvaluationDataError(f"{name} must be an integer >= {minimum}")
    return value


def _number(
    value: object, name: str, minimum: float, maximum: float | None = None
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationDataError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        raise EvaluationDataError(f"{name} is outside its permitted range")
    return number
