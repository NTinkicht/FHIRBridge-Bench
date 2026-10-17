"""Agreement statistics for external projectability-contract review.

These utilities operate only on reviewer labels. They do not import project
renderers, verifier decisions, model outputs, or contract-scoring logic.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class AgreementResult:
    n: int
    labels: tuple[str, ...]
    raw_agreement: float
    cohens_kappa: float
    gwets_ac1: float
    confusion_matrix: dict[str, dict[str, int]]


def _validate(rater_a: list[str], rater_b: list[str]) -> None:
    if len(rater_a) != len(rater_b):
        raise ValueError("reviewer label vectors must have equal length")
    if not rater_a:
        raise ValueError("at least one paired review decision is required")
    if any(not isinstance(value, str) or not value for value in rater_a + rater_b):
        raise ValueError("all reviewer labels must be non-empty strings")


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def agreement_statistics(
    rater_a: Iterable[str],
    rater_b: Iterable[str],
) -> AgreementResult:
    """Compute paired nominal agreement, Cohen's kappa, and Gwet's AC1.

    Gwet's AC1 uses pooled category proportions and the multicategory chance
    agreement term sum(p_k * (1 - p_k)) / (q - 1). For a one-category sample,
    chance agreement is treated as 0 and perfect observed agreement yields 1.
    """

    a = list(rater_a)
    b = list(rater_b)
    _validate(a, b)
    n = len(a)
    labels = tuple(sorted(set(a) | set(b)))

    observed = sum(left == right for left, right in zip(a, b, strict=True)) / n

    counts_a = Counter(a)
    counts_b = Counter(b)
    expected_kappa = sum(
        (counts_a[label] / n) * (counts_b[label] / n) for label in labels
    )
    kappa = _safe_ratio(observed - expected_kappa, 1.0 - expected_kappa)

    if len(labels) == 1:
        expected_ac1 = 0.0
    else:
        pooled = {
            label: (counts_a[label] + counts_b[label]) / (2.0 * n)
            for label in labels
        }
        expected_ac1 = sum(value * (1.0 - value) for value in pooled.values()) / (
            len(labels) - 1
        )
    ac1 = _safe_ratio(observed - expected_ac1, 1.0 - expected_ac1)

    matrix = {left: {right: 0 for right in labels} for left in labels}
    for left, right in zip(a, b, strict=True):
        matrix[left][right] += 1

    return AgreementResult(
        n=n,
        labels=labels,
        raw_agreement=observed,
        cohens_kappa=kappa,
        gwets_ac1=ac1,
        confusion_matrix=matrix,
    )
