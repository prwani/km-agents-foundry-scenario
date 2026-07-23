from __future__ import annotations

import re


EVIDENCE_PENDING = "Evidence pending"


def normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def text_is_evidence_backed(value: str, evidence: str) -> bool:
    normalized_value = normalized_text(value)
    return normalized_value == normalized_text(EVIDENCE_PENDING) or (
        bool(normalized_value) and normalized_value in normalized_text(evidence)
    )
