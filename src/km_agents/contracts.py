from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImplementationKind(StrEnum):
    PROMPT = "prompt"
    HOSTED = "hosted"


class SourceFileKind(StrEnum):
    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    XLSX = "xlsx"


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingCode(StrEnum):
    TEMPLATE_MISMATCH = "template_mismatch"
    PROTECTED_ELEMENT_CHANGED = "protected_element_changed"
    REQUIRED_CONTENT_MISSING = "required_content_missing"
    SENSITIVE_INFORMATION = "sensitive_information"
    CUSTOMER_NAME_NOT_APPROVED = "customer_name_not_approved"
    UNSUPPORTED_EVIDENCE = "unsupported_evidence"
    VISUAL_BRAND_VIOLATION = "visual_brand_violation"
    INVALID_FILE = "invalid_file"
    INCONCLUSIVE = "inconclusive"


class CaseStudyRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    implementation: ImplementationKind = ImplementationKind.HOSTED
    customer_name: str = Field(min_length=1, max_length=120)
    customer_name_approved_for_external_use: bool = False
    opportunity_summary: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=8, max_length=100)

    @property
    def display_customer_name(self) -> str:
        return self.customer_name if self.customer_name_approved_for_external_use else "Customer"


class CaseStudyContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_display_name: str
    title: str
    challenge: str
    solution_overview: str
    architecture_components: list[str] = Field(max_length=6)
    implementation_steps: list[str] = Field(max_length=6)
    measurable_outcomes: list[str] = Field(max_length=4)
    customer_quote: str
    next_steps: list[str] = Field(max_length=4)
    provenance_files: list[str]


class ValidationFinding(BaseModel):
    code: FindingCode
    severity: FindingSeverity
    message: str
    slide_number: int | None = Field(default=None, ge=1)
    shape_name: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    approved: bool
    findings: tuple[ValidationFinding, ...] = ()
    policy_version: str

    @classmethod
    def approved_result(cls, policy_version: str = "1.0.0") -> "ValidationResult":
        return cls(approved=True, findings=(), policy_version=policy_version)

    @classmethod
    def rejected(cls, *reasons: str, policy_version: str = "1.0.0") -> "ValidationResult":
        findings = tuple(
            ValidationFinding(
                code=FindingCode.INCONCLUSIVE,
                severity=FindingSeverity.ERROR,
                message=reason,
            )
            for reason in reasons
            if reason
        )
        return cls(approved=False, findings=findings, policy_version=policy_version)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(finding.message for finding in self.findings)


class ArtifactReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    name: str
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime
    single_use: bool = True

    @model_validator(mode="after")
    def validate_expiry(self) -> "ArtifactReference":
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise ValueError("artifact expiry must be in the future")
        return self


class CaseStudyResponse(BaseModel):
    implementation: ImplementationKind
    correlation_id: str
    status: str
    validation: ValidationResult
    artifact: ArtifactReference | None = None
    repair_attempts: int = Field(default=0, ge=0, le=2)
