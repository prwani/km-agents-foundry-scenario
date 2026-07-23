from __future__ import annotations

import re

from .contracts import (
    CaseStudyRequest,
    FindingCode,
    FindingSeverity,
    ValidationFinding,
    ValidationResult,
)


SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:secret|password|token|api[_ -]?key|connection string)\b", re.IGNORECASE),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:revenue|margin|pipeline|forecast)\s*[:=]\s*\$?\d", re.IGNORECASE),
)


def find_sensitive_markers(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def validate_request(request: CaseStudyRequest) -> ValidationResult:
    findings: list[ValidationFinding] = []
    sensitive = find_sensitive_markers(" ".join([request.opportunity_summary, request.audience]))
    if sensitive:
        findings.append(
            ValidationFinding(
                code=FindingCode.SENSITIVE_INFORMATION,
                severity=FindingSeverity.ERROR,
                message="request text contains potential business-sensitive or credential-like content",
                evidence={"marker_count": len(sensitive)},
            )
        )
    return ValidationResult(
        approved=not findings,
        findings=tuple(findings),
        policy_version="1.0.0",
    )
