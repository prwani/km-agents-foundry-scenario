"""Template-aware PowerPoint generation and validation."""

from .generation import generate_case_study
from .validation import validate_presentation

__all__ = ["generate_case_study", "validate_presentation"]
