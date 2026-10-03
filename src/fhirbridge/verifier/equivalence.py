"""Standard-independent semantic equivalence primitives.

These helpers operate on canonical semantic payloads after target lifting. They
contain no FHIR-path or HL7 v2 field-position logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isclose
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EquivalenceResult:
    equivalent: bool
    rationale_code: str
    details: dict[str, object]


@runtime_checkable
class TerminologyEquivalenceProvider(Protocol):
    """Provider for approved coded-concept equivalence."""

    def equivalent(
        self,
        source_system: str | None,
        source_code: str | None,
        target_system: str | None,
        target_code: str | None,
    ) -> EquivalenceResult:
        ...


@runtime_checkable
class UnitEquivalenceProvider(Protocol):
    """Provider for value+unit equivalence."""

    def equivalent(
        self,
        source_value: float,
        source_unit: str,
        target_value: float,
        target_unit: str,
    ) -> EquivalenceResult:
        ...


class ExactTerminologyEquivalence:
    """Baseline provider accepting exact system/code identity only."""

    def equivalent(
        self,
        source_system: str | None,
        source_code: str | None,
        target_system: str | None,
        target_code: str | None,
    ) -> EquivalenceResult:
        same = source_system == target_system and source_code == target_code
        return EquivalenceResult(
            equivalent=same,
            rationale_code="EXACT_CODE_MATCH" if same else "CODE_MISMATCH",
            details={
                "source_system": source_system,
                "source_code": source_code,
                "target_system": target_system,
                "target_code": target_code,
            },
        )


class ExactUnitEquivalence:
    """Baseline value+unit provider without UCUM conversion.

    Production verifier qualification must replace or wrap this provider with a
    pinned UCUM implementation for rules that license unit conversion.
    """

    def __init__(self, *, rel_tol: float = 0.0, abs_tol: float = 0.0) -> None:
        self.rel_tol = rel_tol
        self.abs_tol = abs_tol

    def equivalent(
        self,
        source_value: float,
        source_unit: str,
        target_value: float,
        target_unit: str,
    ) -> EquivalenceResult:
        units_match = source_unit == target_unit
        values_match = isclose(
            source_value,
            target_value,
            rel_tol=self.rel_tol,
            abs_tol=self.abs_tol,
        )
        equivalent = units_match and values_match
        return EquivalenceResult(
            equivalent=equivalent,
            rationale_code="EXACT_QUANTITY_MATCH" if equivalent else "QUANTITY_MISMATCH",
            details={
                "source_value": source_value,
                "source_unit": source_unit,
                "target_value": target_value,
                "target_unit": target_unit,
                "units_match": units_match,
                "values_match": values_match,
            },
        )


def identifiers_equivalent(
    source: dict[str, object],
    target: dict[str, object],
    *,
    allow_namespace_change: bool = False,
) -> EquivalenceResult:
    """Compare identifier value and namespace/system semantics."""

    value_match = source.get("value") == target.get("value")
    namespace_match = source.get("system") == target.get("system")
    equivalent = value_match and (namespace_match or allow_namespace_change)

    if not value_match:
        rationale = "IDENTIFIER_VALUE_MISMATCH"
    elif not namespace_match and not allow_namespace_change:
        rationale = "IDENTIFIER_NAMESPACE_MISMATCH"
    elif not namespace_match:
        rationale = "DECLARED_IDENTIFIER_NAMESPACE_CHANGE"
    else:
        rationale = "EXACT_IDENTIFIER_MATCH"

    return EquivalenceResult(
        equivalent=equivalent,
        rationale_code=rationale,
        details={
            "source_value": source.get("value"),
            "target_value": target.get("value"),
            "source_system": source.get("system"),
            "target_system": target.get("system"),
            "namespace_change_allowed": allow_namespace_change,
        },
    )


def normalize_datetime(value: str) -> datetime:
    """Normalize an ISO-8601 timestamp to an aware UTC datetime.

    Naive datetimes are rejected rather than silently assigned a timezone.
    """

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timezone required for instant comparison: {value!r}")
    return parsed.astimezone(UTC)


def instants_equivalent(source: str, target: str) -> EquivalenceResult:
    """Compare two ISO-8601 instants after timezone normalization."""

    source_dt = normalize_datetime(source)
    target_dt = normalize_datetime(target)
    equivalent = source_dt == target_dt
    return EquivalenceResult(
        equivalent=equivalent,
        rationale_code="SAME_INSTANT" if equivalent else "TEMPORAL_INSTANT_MISMATCH",
        details={
            "source_utc": source_dt.isoformat(),
            "target_utc": target_dt.isoformat(),
        },
    )
