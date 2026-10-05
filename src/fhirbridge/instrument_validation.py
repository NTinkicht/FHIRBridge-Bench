"""Binary qualification metrics for the semantic verifier.

The core confirmatory qualification question is whether a transformation
contains at least one major semantic-fidelity error. This module compares the
frozen verifier's binary verdict with the sealed, adjudicated expert standard.
No acceptance threshold is hard-coded here; thresholds are supplied only after
pilot calibration and preregistration.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt

_Z_95 = 1.959963984540054


@dataclass(frozen=True)
class ConfidenceInterval:
    estimate: float
    lower: float
    upper: float


@dataclass(frozen=True)
class ConfusionCounts:
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int

    @property
    def total(self) -> int:
        return (
            self.true_positive
            + self.true_negative
            + self.false_positive
            + self.false_negative
        )


@dataclass(frozen=True)
class InstrumentQualification:
    counts: ConfusionCounts
    sensitivity: ConfidenceInterval
    specificity: ConfidenceInterval
    ppv: ConfidenceInterval
    npv: ConfidenceInterval
    accuracy: ConfidenceInterval


@dataclass(frozen=True)
class QualificationGate:
    passed: bool
    sensitivity_threshold: float
    ppv_threshold: float
    use_lower_confidence_bound: bool
    sensitivity_value: float
    ppv_value: float


def _validate_binary(values: list[bool], name: str) -> None:
    if not values:
        raise ValueError(f"{name} must not be empty")
    if any(type(value) is not bool for value in values):
        raise ValueError(f"{name} must contain booleans only")


def _wilson(successes: int, total: int, *, z: float = _Z_95) -> ConfidenceInterval:
    if total <= 0:
        raise ValueError("metric denominator must be positive")
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
    return ConfidenceInterval(
        estimate=estimate,
        lower=max(0.0, centre - half_width),
        upper=min(1.0, centre + half_width),
    )


def confusion_counts(
    expert_major_error: Iterable[bool],
    verifier_major_error: Iterable[bool],
) -> ConfusionCounts:
    """Build binary confusion counts using expert adjudication as reference."""

    expert = list(expert_major_error)
    verifier = list(verifier_major_error)
    _validate_binary(expert, "expert_major_error")
    _validate_binary(verifier, "verifier_major_error")
    if len(expert) != len(verifier):
        raise ValueError("expert and verifier vectors must have equal length")

    tp = tn = fp = fn = 0
    for truth, prediction in zip(expert, verifier, strict=True):
        if truth and prediction:
            tp += 1
        elif not truth and not prediction:
            tn += 1
        elif not truth and prediction:
            fp += 1
        else:
            fn += 1

    return ConfusionCounts(
        true_positive=tp,
        true_negative=tn,
        false_positive=fp,
        false_negative=fn,
    )


def qualify_instrument(
    expert_major_error: Iterable[bool],
    verifier_major_error: Iterable[bool],
) -> InstrumentQualification:
    """Calculate sealed-set binary instrument validity estimates with 95% CIs."""

    counts = confusion_counts(expert_major_error, verifier_major_error)
    positives = counts.true_positive + counts.false_negative
    negatives = counts.true_negative + counts.false_positive
    predicted_positive = counts.true_positive + counts.false_positive
    predicted_negative = counts.true_negative + counts.false_negative

    if positives == 0:
        raise ValueError("sensitivity is undefined because expert positives are absent")
    if negatives == 0:
        raise ValueError("specificity is undefined because expert negatives are absent")
    if predicted_positive == 0:
        raise ValueError("PPV is undefined because verifier positives are absent")
    if predicted_negative == 0:
        raise ValueError("NPV is undefined because verifier negatives are absent")

    return InstrumentQualification(
        counts=counts,
        sensitivity=_wilson(counts.true_positive, positives),
        specificity=_wilson(counts.true_negative, negatives),
        ppv=_wilson(counts.true_positive, predicted_positive),
        npv=_wilson(counts.true_negative, predicted_negative),
        accuracy=_wilson(
            counts.true_positive + counts.true_negative,
            counts.total,
        ),
    )


def evaluate_gate(
    qualification: InstrumentQualification,
    *,
    minimum_sensitivity: float,
    minimum_ppv: float,
    use_lower_confidence_bound: bool = False,
) -> QualificationGate:
    """Evaluate preregistered acceptance thresholds without embedding defaults."""

    for name, threshold in (
        ("minimum_sensitivity", minimum_sensitivity),
        ("minimum_ppv", minimum_ppv),
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")

    sensitivity_value = (
        qualification.sensitivity.lower
        if use_lower_confidence_bound
        else qualification.sensitivity.estimate
    )
    ppv_value = (
        qualification.ppv.lower
        if use_lower_confidence_bound
        else qualification.ppv.estimate
    )
    return QualificationGate(
        passed=(
            sensitivity_value >= minimum_sensitivity
            and ppv_value >= minimum_ppv
        ),
        sensitivity_threshold=minimum_sensitivity,
        ppv_threshold=minimum_ppv,
        use_lower_confidence_bound=use_lower_confidence_bound,
        sensitivity_value=sensitivity_value,
        ppv_value=ppv_value,
    )
