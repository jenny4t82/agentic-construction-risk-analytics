"""Project-defined construction risk scoring rules.

This is an educational project formula, not an official OSHA calculation or
regulatory safety standard.
"""

from typing import Final


RISK_BANDS: Final[tuple[tuple[int, int, str], ...]] = (
    (1, 19, "Low"),
    (20, 39, "Moderate"),
    (40, 69, "High"),
    (70, 100, "Critical"),
)


def calculate_risk_score(severity: int, likelihood: int, exposure: int) -> int:
    """Return the project-defined score: severity × likelihood × exposure."""

    _validate_scale("severity", severity, 5)
    _validate_scale("likelihood", likelihood, 5)
    _validate_scale("exposure", exposure, 4)
    return severity * likelihood * exposure


def risk_band(score: int) -> str:
    """Convert a score from 1–100 into the project's named band."""

    if not 1 <= score <= 100:
        raise ValueError("risk score must be between 1 and 100")
    for minimum, maximum, band in RISK_BANDS:
        if minimum <= score <= maximum:
            return band
    raise ValueError(f"no risk band configured for score {score}")


def _validate_scale(name: str, value: int, maximum: int) -> None:
    if not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 1 to {maximum}")
