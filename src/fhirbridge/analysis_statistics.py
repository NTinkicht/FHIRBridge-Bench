"""Pre-registered statistical utilities for FHIRBridge confirmatory analysis.

The functions are deliberately dependency-light and operate on analysis-ready
vectors. Construction of the analysis set (for example, which paired cases are
structurally valid and determinate in both arms) must be frozen separately.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class IntervalEstimate:
    estimate: float
    lower: float
    upper: float
    method: str


@dataclass(frozen=True)
class PairedRiskDifference:
    n: int
    risk_a: float
    risk_b: float
    difference: float
    a_positive_b_negative: int
    a_negative_b_positive: int


@dataclass(frozen=True)
class ClusterBootstrapResult:
    estimate: float
    lower: float
    upper: float
    iterations: int
    seed: int
    cluster_count: int
    method: str = "paired_cluster_percentile_bootstrap_95"


@dataclass(frozen=True)
class McNemarResult:
    discordant_pairs: int
    a_positive_b_negative: int
    a_negative_b_positive: int
    p_value: float
    method: str = "two_sided_exact_binomial_mcnemar"


def _binary(values: Iterable[bool | int], name: str) -> list[int]:
    result: list[int] = []
    for value in values:
        if type(value) is bool:
            result.append(int(value))
        elif type(value) is int and value in {0, 1}:
            result.append(value)
        else:
            raise ValueError(f"{name} must contain only booleans or 0/1 integers")
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> IntervalEstimate:
    """Wilson score interval for a binomial proportion."""

    if type(successes) is not int or type(total) is not int:
        raise ValueError("successes and total must be integers")
    if total <= 0:
        raise ValueError("total must be positive")
    if not 0 <= successes <= total:
        raise ValueError("successes must be in [0,total]")
    if z <= 0:
        raise ValueError("z must be positive")

    p = successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    half = (
        z
        * math.sqrt((p * (1.0 - p) / total) + z2 / (4.0 * total * total))
        / denominator
    )
    return IntervalEstimate(
        estimate=p,
        lower=max(0.0, center - half),
        upper=min(1.0, center + half),
        method="Wilson_95_percent",
    )


def paired_risk_difference(
    outcome_a: Iterable[bool | int],
    outcome_b: Iterable[bool | int],
) -> PairedRiskDifference:
    """Absolute paired risk difference A-B on an already frozen paired subset."""

    a = _binary(outcome_a, "outcome_a")
    b = _binary(outcome_b, "outcome_b")
    if len(a) != len(b):
        raise ValueError("paired outcome vectors must have equal length")

    n = len(a)
    a_pos_b_neg = sum(
        left == 1 and right == 0 for left, right in zip(a, b, strict=True)
    )
    a_neg_b_pos = sum(
        left == 0 and right == 1 for left, right in zip(a, b, strict=True)
    )
    risk_a = sum(a) / n
    risk_b = sum(b) / n
    return PairedRiskDifference(
        n=n,
        risk_a=risk_a,
        risk_b=risk_b,
        difference=risk_a - risk_b,
        a_positive_b_negative=a_pos_b_neg,
        a_negative_b_positive=a_neg_b_pos,
    )


def exact_mcnemar(
    outcome_a: Iterable[bool | int],
    outcome_b: Iterable[bool | int],
) -> McNemarResult:
    """Two-sided exact McNemar test using the discordant-pair binomial law."""

    summary = paired_risk_difference(outcome_a, outcome_b)
    b = summary.a_positive_b_negative
    c = summary.a_negative_b_positive
    discordant = b + c
    if discordant == 0:
        p_value = 1.0
    else:
        tail_k = min(b, c)
        lower_tail = sum(
            math.comb(discordant, k) for k in range(tail_k + 1)
        ) / (2.0**discordant)
        p_value = min(1.0, 2.0 * lower_tail)
    return McNemarResult(
        discordant_pairs=discordant,
        a_positive_b_negative=b,
        a_negative_b_positive=c,
        p_value=p_value,
    )


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0,1]")
    if not sorted_values:
        raise ValueError("cannot compute percentile of empty values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    weight = position - lower_index
    return (
        sorted_values[lower_index] * (1.0 - weight)
        + sorted_values[upper_index] * weight
    )


def clustered_paired_risk_difference_bootstrap(
    outcome_a: Iterable[bool | int],
    outcome_b: Iterable[bool | int],
    cluster_ids: Iterable[str],
    *,
    iterations: int = 10_000,
    seed: int,
) -> ClusterBootstrapResult:
    """Percentile bootstrap resampling source clusters, retaining paired rows."""

    a = _binary(outcome_a, "outcome_a")
    b = _binary(outcome_b, "outcome_b")
    clusters = list(cluster_ids)
    if len(a) != len(b) or len(a) != len(clusters):
        raise ValueError("outcomes and cluster_ids must have equal length")
    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    if any(not isinstance(cluster, str) or not cluster for cluster in clusters):
        raise ValueError("cluster_ids must be non-empty strings")

    rows_by_cluster: dict[str, list[int]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        rows_by_cluster[cluster].append(index)
    unique_clusters = sorted(rows_by_cluster)
    if len(unique_clusters) < 2:
        raise ValueError("cluster bootstrap requires at least two clusters")

    point = paired_risk_difference(a, b).difference
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(iterations):
        sampled_clusters = [
            rng.choice(unique_clusters) for _ in range(len(unique_clusters))
        ]
        sampled_indices: list[int] = []
        for cluster in sampled_clusters:
            sampled_indices.extend(rows_by_cluster[cluster])
        sampled_a = [a[index] for index in sampled_indices]
        sampled_b = [b[index] for index in sampled_indices]
        estimates.append(
            paired_risk_difference(sampled_a, sampled_b).difference
        )

    estimates.sort()
    return ClusterBootstrapResult(
        estimate=point,
        lower=_percentile(estimates, 0.025),
        upper=_percentile(estimates, 0.975),
        iterations=iterations,
        seed=seed,
        cluster_count=len(unique_clusters),
    )


def holm_adjust(p_values: Iterable[float]) -> tuple[float, ...]:
    """Holm family-wise adjusted p-values in original input order."""

    values = list(p_values)
    if not values:
        raise ValueError("p_values must not be empty")
    if any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in values):
        raise ValueError("all p-values must be numeric in [0,1]")

    ordered = sorted(enumerate(values), key=lambda item: item[1])
    adjusted_by_index: dict[int, float] = {}
    running = 0.0
    m = len(values)
    for rank, (original_index, value) in enumerate(ordered):
        candidate = min(1.0, (m - rank) * float(value))
        running = max(running, candidate)
        adjusted_by_index[original_index] = running
    return tuple(adjusted_by_index[index] for index in range(m))
