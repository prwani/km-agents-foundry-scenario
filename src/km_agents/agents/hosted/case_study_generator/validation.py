from __future__ import annotations

import json
import os
from pathlib import Path
import re

from agent_framework import tool
from pptx import Presentation

from km_agents.agents.hosted.case_study_generator.operations import extract_source_text
from km_agents.contracts import (
    CaseStudyRequest,
    FindingCode,
    FindingSeverity,
    ValidationFinding,
    ValidationResult,
)
from km_agents.grounding import EVIDENCE_PENDING, text_is_evidence_backed
from km_agents.pptx_skill.validation import validate_presentation


def workspace_deck_path(relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Deck path must be relative to the hosted session workspace")
    workspace = Path(os.getenv("AGENT_WORKSPACE_ROOT", str(Path.home() / "data"))).resolve()
    candidate = (workspace / relative_path).resolve()
    if workspace not in candidate.parents or candidate.suffix.lower() != ".pptx":
        raise ValueError("Deck path must resolve to a PPTX inside the hosted session workspace")
    if not candidate.is_file():
        raise FileNotFoundError(f"Deck is missing from the hosted session workspace: {relative_path}")
    return candidate


def _editable_content_segments(shape: object) -> list[str]:
    text = shape.text.strip()
    if not text:
        return []
    return [
        re.sub(r"^\d+\.\s*", "", segment).strip()
        for segment in re.split(r"[\n•]+|\s(?=\d+\.\s)", text)
        if segment.strip()
    ]


def _is_template_boilerplate(shape_name: str, value: str, request: CaseStudyRequest) -> bool:
    if shape_name == "editable:s1:customer-name":
        return value == request.display_customer_name
    if shape_name == "editable:s1:subtitle":
        return value == "A synthetic customer success story"
    if shape_name == "editable:s2:context":
        return value == "Evidence-backed modernization opportunity"
    return shape_name == "editable:s7:quote-attribution" and value == (
        f"{request.display_customer_name} stakeholder"
    )


def _source_form(value: str, request: CaseStudyRequest) -> str:
    if request.customer_name_approved_for_external_use:
        return value
    return re.sub(
        re.escape(request.display_customer_name),
        request.customer_name,
        value,
        flags=re.IGNORECASE,
    )


def validate_case_study_deck(
    deck_path: Path,
    request: CaseStudyRequest,
    evidence_paths: list[str],
) -> ValidationResult:
    policy_path = Path(
        os.getenv("TEMPLATE_POLICY_PATH", "assets/templates/contoso-template-policy.json")
    )
    result = validate_presentation(deck_path=deck_path, policy_path=policy_path, request=request)
    findings = list(result.findings)
    if not evidence_paths:
        findings.append(
            ValidationFinding(
                code=FindingCode.INCONCLUSIVE,
                severity=FindingSeverity.ERROR,
                message="Evidence paths are required for source-grounded validation",
            )
        )
    elif result.approved:
        try:
            evidence = "\n".join(extract_source_text(path) for path in evidence_paths)
        except (FileNotFoundError, ValueError) as exc:
            findings.append(
                ValidationFinding(
                    code=FindingCode.INCONCLUSIVE,
                    severity=FindingSeverity.ERROR,
                    message=f"Source-grounding validation could not read the uploaded evidence: {exc}",
                )
            )
        else:
            presentation = Presentation(deck_path)
            for slide_number, slide in enumerate(presentation.slides, start=1):
                for shape in slide.shapes:
                    if not shape.name.startswith("editable:") or not getattr(shape, "has_text_frame", False):
                        continue
                    for value in _editable_content_segments(shape):
                        if _is_template_boilerplate(shape.name, value, request):
                            continue
                        if value == EVIDENCE_PENDING or text_is_evidence_backed(
                            _source_form(value, request),
                            evidence,
                        ):
                            continue
                        findings.append(
                            ValidationFinding(
                                code=FindingCode.UNSUPPORTED_EVIDENCE,
                                severity=FindingSeverity.ERROR,
                                message="Deck contains content not supported by uploaded evidence",
                                slide_number=slide_number,
                                shape_name=shape.name,
                            )
                        )
    return ValidationResult(
        approved=not findings,
        findings=tuple(findings),
        policy_version=result.policy_version,
    )


@tool(
    name="validate_case_study_deck",
    description=(
        "Deterministically validate a session PPTX against the canonical template, safety policy, "
        "and the source evidence paths used to create it."
    ),
    approval_mode="never_require",
)
def validate_case_study_deck_tool(
    relative_deck_path: str,
    request_json: str,
    source_paths_json: str,
) -> str:
    request = CaseStudyRequest.model_validate_json(request_json)
    source_paths = json.loads(source_paths_json)
    if not isinstance(source_paths, list) or not all(isinstance(path, str) for path in source_paths):
        raise ValueError("source_paths_json must be a JSON array of session workspace paths")
    result = validate_case_study_deck(
        workspace_deck_path(relative_deck_path),
        request,
        source_paths,
    )
    return result.model_dump_json()
