"""Qualification harness for the candidate UCUM quantity-equivalence provider.

The project-specific laboratory matrix supplements the official UCUM functional
suite. Passing this module's matrix is necessary but not sufficient for
confirmatory freeze.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .verifier.equivalence import UnitEquivalenceProvider


@dataclass(frozen=True)
class UnitQualificationCase:
    case_id: str
    source_value: float
    source_unit: str
    target_value: float
    target_unit: str
    expected_equivalent: bool
    rationale: str


@dataclass(frozen=True)
class UnitQualificationOutcome:
    case_id: str
    expected_equivalent: bool
    observed_equivalent: bool | None
    passed: bool
    provider_rationale_code: str | None
    exception: str | None


@dataclass(frozen=True)
class UnitQualificationReport:
    matrix_id: str
    matrix_version: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    all_passed: bool
    outcomes: tuple[UnitQualificationOutcome, ...]


def _number(value: object, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    return float(value)


def load_unit_qualification_cases(
    document: dict[str, Any],
) -> tuple[str, str, tuple[UnitQualificationCase, ...]]:
    """Parse and validate the project laboratory conversion matrix."""

    matrix = document.get("matrix")
    cases = document.get("cases")
    if not isinstance(matrix, dict):
        raise ValueError("UCUM matrix must contain a matrix mapping")
    if not isinstance(cases, list) or not cases:
        raise ValueError("UCUM matrix must contain at least one case")

    matrix_id = matrix.get("id")
    matrix_version = matrix.get("version")
    if not isinstance(matrix_id, str) or not matrix_id:
        raise ValueError("matrix.id must be a non-empty string")
    if not isinstance(matrix_version, str) or not matrix_version:
        raise ValueError("matrix.version must be a non-empty string")

    parsed: list[UnitQualificationCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ValueError(f"cases[{index}] must be a mapping")
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"cases[{index}].case_id must be a non-empty string")
        if case_id in seen_ids:
            raise ValueError(f"duplicate UCUM qualification case_id: {case_id}")
        seen_ids.add(case_id)

        source = item.get("source")
        target = item.get("target")
        if not isinstance(source, dict) or not isinstance(target, dict):
            raise ValueError(f"{case_id} source and target must be mappings")
        source_unit = source.get("unit")
        target_unit = target.get("unit")
        if not isinstance(source_unit, str) or not source_unit:
            raise ValueError(f"{case_id} source.unit must be non-empty")
        if not isinstance(target_unit, str) or not target_unit:
            raise ValueError(f"{case_id} target.unit must be non-empty")

        expected = item.get("expected_equivalent")
        if not isinstance(expected, bool):
            raise ValueError(f"{case_id} expected_equivalent must be boolean")
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale:
            raise ValueError(f"{case_id} rationale must be non-empty")

        parsed.append(
            UnitQualificationCase(
                case_id=case_id,
                source_value=_number(source.get("value"), path=f"{case_id}.source.value"),
                source_unit=source_unit,
                target_value=_number(target.get("value"), path=f"{case_id}.target.value"),
                target_unit=target_unit,
                expected_equivalent=expected,
                rationale=rationale,
            )
        )

    return matrix_id, matrix_version, tuple(parsed)


def qualify_unit_provider(
    provider: UnitEquivalenceProvider,
    document: dict[str, Any],
) -> UnitQualificationReport:
    """Run every project matrix case and retain failures for audit."""

    matrix_id, matrix_version, cases = load_unit_qualification_cases(document)
    outcomes: list[UnitQualificationOutcome] = []

    for case in cases:
        try:
            result = provider.equivalent(
                case.source_value,
                case.source_unit,
                case.target_value,
                case.target_unit,
            )
            observed = result.equivalent
            passed = observed is case.expected_equivalent
            outcomes.append(
                UnitQualificationOutcome(
                    case_id=case.case_id,
                    expected_equivalent=case.expected_equivalent,
                    observed_equivalent=observed,
                    passed=passed,
                    provider_rationale_code=result.rationale_code,
                    exception=None,
                )
            )
        except Exception as exc:  # qualification records provider failures
            outcomes.append(
                UnitQualificationOutcome(
                    case_id=case.case_id,
                    expected_equivalent=case.expected_equivalent,
                    observed_equivalent=None,
                    passed=False,
                    provider_rationale_code=None,
                    exception=f"{type(exc).__name__}: {exc}",
                )
            )

    passed_cases = sum(outcome.passed for outcome in outcomes)
    return UnitQualificationReport(
        matrix_id=matrix_id,
        matrix_version=matrix_version,
        total_cases=len(outcomes),
        passed_cases=passed_cases,
        failed_cases=len(outcomes) - passed_cases,
        all_passed=passed_cases == len(outcomes),
        outcomes=tuple(outcomes),
    )
