"""Qualification summaries for seeded semantic-fault stimuli.

Seeded faults are supporting evidence that the verifier responds to known
perturbations. They do not replace blinded expert adjudication of naturally
occurring model errors. This module therefore reports detection performance
without embedding any acceptance threshold or treating the mutation manifest as
proof of full verifier validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

_Z_95 = 1.959963984540054
_ERROR_CLASSES = frozenset(
    {"FABRICATION", "CORRUPTION", "OMISSION", "MISATTRIBUTION", "STRUCTURAL_ERROR"}
)
_SEVERITY_ORDER = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}


@dataclass(frozen=True)
class RateEstimate:
    successes: int
    total: int
    estimate: float
    lower: float
    upper: float


@dataclass(frozen=True)
class FaultQualificationCase:
    """One seeded-fault run paired with the verifier/structural-gate outcome."""

    case_id: str
    expected_classifications: tuple[str, ...]
    expected_severity: str
    observed_classifications: tuple[str, ...]
    observed_severities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("case_id must be non-empty")
        if not self.expected_classifications:
            raise ValueError("expected_classifications must not be empty")
        unknown_expected = set(self.expected_classifications) - _ERROR_CLASSES
        if unknown_expected:
            raise ValueError(
                "unsupported expected classifications: "
                + ", ".join(sorted(unknown_expected))
            )
        if self.expected_severity not in _SEVERITY_ORDER:
            raise ValueError("expected_severity must be one of S0, S1, S2, S3")
        unknown_observed_severity = set(self.observed_severities) - set(_SEVERITY_ORDER)
        if unknown_observed_severity:
            raise ValueError(
                "unsupported observed severities: "
                + ", ".join(sorted(unknown_observed_severity))
            )

    @property
    def observed_error_classes(self) -> frozenset[str]:
        return frozenset(
            classification
            for classification in self.observed_classifications
            if classification in _ERROR_CLASSES
        )

    @property
    def expected_error_classes(self) -> frozenset[str]:
        return frozenset(self.expected_classifications)

    @property
    def detects_all_expected_classes(self) -> bool:
        return self.expected_error_classes <= self.observed_error_classes

    @property
    def exact_class_resolution(self) -> bool:
        return self.expected_error_classes == self.observed_error_classes

    @property
    def maximum_observed_severity(self) -> str | None:
        if not self.observed_severities:
            return None
        return max(self.observed_severities, key=_SEVERITY_ORDER.__getitem__)

    @property
    def severity_at_least_expected(self) -> bool:
        observed = self.maximum_observed_severity
        if observed is None:
            return False
        return _SEVERITY_ORDER[observed] >= _SEVERITY_ORDER[self.expected_severity]


@dataclass(frozen=True)
class FaultQualificationReport:
    total_cases: int
    exact_class_resolution: RateEstimate
    all_expected_classes_detected: RateEstimate
    severity_at_least_expected: RateEstimate
    by_class: dict[str, RateEstimate]
    by_expected_severity: dict[str, RateEstimate]
    unresolved_case_ids: tuple[str, ...]
    extra_error_case_ids: tuple[str, ...]


def _wilson(successes: int, total: int, *, z: float = _Z_95) -> RateEstimate:
    if total <= 0:
        raise ValueError("rate denominator must be positive")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")

    estimate = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    centre = (estimate + z2 / (2.0 * total)) / denominator
    half_width = (
        z
        * sqrt(
            estimate * (1.0 - estimate) / total
            + z2 / (4.0 * total * total)
        )
        / denominator
    )
    return RateEstimate(
        successes=successes,
        total=total,
        estimate=estimate,
        lower=max(0.0, centre - half_width),
        upper=min(1.0, centre + half_width),
    )


def _rate(values: list[bool]) -> RateEstimate:
    if not values:
        raise ValueError("rate requires at least one case")
    return _wilson(sum(values), len(values))


def qualify_seeded_faults(
    cases: list[FaultQualificationCase],
) -> FaultQualificationReport:
    """Summarize known-fault responsiveness with Wilson 95% intervals.

    Class-wise sensitivity is calculated only among cases in which that class is
    expected. Severity strata report whether every expected error class was
    detected for cases whose seeded maximum severity equals the named stratum.
    Extra detected error classes are reported separately and make strict class
    resolution fail, but they do not erase detection of an expected class.
    """

    if not cases:
        raise ValueError("cases must not be empty")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_id values must be unique")

    by_class: dict[str, RateEstimate] = {}
    for classification in sorted(_ERROR_CLASSES):
        relevant = [
            case
            for case in cases
            if classification in case.expected_error_classes
        ]
        if relevant:
            by_class[classification] = _rate(
                [classification in case.observed_error_classes for case in relevant]
            )

    by_expected_severity: dict[str, RateEstimate] = {}
    for severity in _SEVERITY_ORDER:
        relevant = [case for case in cases if case.expected_severity == severity]
        if relevant:
            by_expected_severity[severity] = _rate(
                [case.detects_all_expected_classes for case in relevant]
            )

    unresolved = tuple(
        sorted(case.case_id for case in cases if not case.detects_all_expected_classes)
    )
    extras = tuple(
        sorted(
            case.case_id
            for case in cases
            if case.observed_error_classes - case.expected_error_classes
        )
    )

    return FaultQualificationReport(
        total_cases=len(cases),
        exact_class_resolution=_rate(
            [case.exact_class_resolution for case in cases]
        ),
        all_expected_classes_detected=_rate(
            [case.detects_all_expected_classes for case in cases]
        ),
        severity_at_least_expected=_rate(
            [case.severity_at_least_expected for case in cases]
        ),
        by_class=by_class,
        by_expected_severity=by_expected_severity,
        unresolved_case_ids=unresolved,
        extra_error_case_ids=extras,
    )
