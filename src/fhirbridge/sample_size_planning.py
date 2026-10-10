"""Pilot-driven sample-size planning utilities.

These functions support pre-confirmatory planning. They do not change the
confirmatory estimands or tests. In particular, McNemar sizing is an
asymptotic planning approximation while confirmatory paired testing remains the
two-sided exact binomial McNemar procedure frozen in the SAP.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True)
class PrecisionPlan:
    independent_n: int
    cluster_inflated_n: int
    attempted_n: int
    expected_rate: float
    target_half_width: float
    confidence_level: float
    design_effect: float
    expected_analysis_retention: float


@dataclass(frozen=True)
class PairedMcNemarPlan:
    pair_n_independent: int
    cluster_inflated_pair_n: int
    attempted_pair_n: int
    p10: float
    p01: float
    absolute_risk_difference: float
    discordant_probability: float
    alpha: float
    power: float
    design_effect: float
    expected_pair_retention: float
    method: str = "normal_approximation_for_planning_only"


def _probability(value: float, *, name: str, open_zero: bool = False) -> None:
    lower_ok = value > 0 if open_zero else value >= 0
    if not lower_ok or value > 1:
        bracket = "(0,1]" if open_zero else "[0,1]"
        raise ValueError(f"{name} must be in {bracket}")


def z_for_confidence(confidence_level: float) -> float:
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be in (0,1)")
    return NormalDist().inv_cdf(0.5 + confidence_level / 2.0)


def wilson_expected_half_width(
    sample_size: int,
    expected_rate: float,
    *,
    confidence_level: float = 0.95,
) -> float:
    """Expected Wilson half-width using a continuous planning proportion."""

    if type(sample_size) is not int or sample_size <= 0:
        raise ValueError("sample_size must be a positive integer")
    _probability(expected_rate, name="expected_rate")
    z = z_for_confidence(confidence_level)
    z2 = z * z
    denominator = 1.0 + z2 / sample_size
    half = (
        z
        * math.sqrt(
            expected_rate * (1.0 - expected_rate) / sample_size
            + z2 / (4.0 * sample_size * sample_size)
        )
        / denominator
    )
    return half


def minimum_n_for_wilson_precision(
    expected_rate: float,
    target_half_width: float,
    *,
    confidence_level: float = 0.95,
    maximum_n: int = 10_000_000,
) -> int:
    """Smallest independent-observation N meeting expected Wilson precision."""

    _probability(expected_rate, name="expected_rate")
    if not 0 < target_half_width < 1:
        raise ValueError("target_half_width must be in (0,1)")
    if type(maximum_n) is not int or maximum_n < 1:
        raise ValueError("maximum_n must be a positive integer")

    if wilson_expected_half_width(
        maximum_n,
        expected_rate,
        confidence_level=confidence_level,
    ) > target_half_width:
        raise ValueError("maximum_n is insufficient for requested precision")

    low, high = 1, maximum_n
    while low < high:
        mid = (low + high) // 2
        if (
            wilson_expected_half_width(
                mid,
                expected_rate,
                confidence_level=confidence_level,
            )
            <= target_half_width
        ):
            high = mid
        else:
            low = mid + 1
    return low


def cluster_design_effect(mean_cluster_size: float, icc: float) -> float:
    """Exchangeable-cluster design effect: 1 + (m-1) * ICC."""

    if mean_cluster_size < 1:
        raise ValueError("mean_cluster_size must be >= 1")
    _probability(icc, name="icc")
    return 1.0 + (mean_cluster_size - 1.0) * icc


def inflate_required_n(
    independent_n: int,
    *,
    design_effect: float,
    expected_analysis_retention: float,
) -> tuple[int, int]:
    """Return cluster-inflated and attempted sample sizes."""

    if type(independent_n) is not int or independent_n <= 0:
        raise ValueError("independent_n must be a positive integer")
    if design_effect < 1:
        raise ValueError("design_effect must be >= 1")
    _probability(
        expected_analysis_retention,
        name="expected_analysis_retention",
        open_zero=True,
    )
    clustered = math.ceil(independent_n * design_effect)
    attempted = math.ceil(clustered / expected_analysis_retention)
    return clustered, attempted


def plan_proportion_precision(
    *,
    expected_rate: float,
    target_half_width: float,
    mean_cluster_size: float,
    icc: float,
    expected_analysis_retention: float,
    confidence_level: float = 0.95,
) -> PrecisionPlan:
    independent_n = minimum_n_for_wilson_precision(
        expected_rate,
        target_half_width,
        confidence_level=confidence_level,
    )
    design_effect = cluster_design_effect(mean_cluster_size, icc)
    clustered, attempted = inflate_required_n(
        independent_n,
        design_effect=design_effect,
        expected_analysis_retention=expected_analysis_retention,
    )
    return PrecisionPlan(
        independent_n=independent_n,
        cluster_inflated_n=clustered,
        attempted_n=attempted,
        expected_rate=expected_rate,
        target_half_width=target_half_width,
        confidence_level=confidence_level,
        design_effect=design_effect,
        expected_analysis_retention=expected_analysis_retention,
    )


def approximate_mcnemar_pair_n(
    *,
    p10: float,
    p01: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Approximate paired N for McNemar planning from discordant probabilities.

    p10 = P(A positive, B negative)
    p01 = P(A negative, B positive)
    """

    _probability(p10, name="p10")
    _probability(p01, name="p01")
    if p10 + p01 > 1:
        raise ValueError("p10 + p01 must be <= 1")
    if p10 == p01:
        raise ValueError("McNemar planning requires a nonzero discordant difference")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    if not 0 < power < 1:
        raise ValueError("power must be in (0,1)")

    discordant = p10 + p01
    difference = abs(p10 - p01)
    z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    z_power = NormalDist().inv_cdf(power)
    variance_alt = max(discordant - difference * difference, 0.0)
    numerator = (
        z_alpha * math.sqrt(discordant)
        + z_power * math.sqrt(variance_alt)
    ) ** 2
    return max(2, math.ceil(numerator / (difference * difference)))


def plan_paired_mcnemar(
    *,
    p10: float,
    p01: float,
    mean_cluster_size: float,
    icc: float,
    expected_pair_retention: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> PairedMcNemarPlan:
    independent_n = approximate_mcnemar_pair_n(
        p10=p10,
        p01=p01,
        alpha=alpha,
        power=power,
    )
    design_effect = cluster_design_effect(mean_cluster_size, icc)
    clustered, attempted = inflate_required_n(
        independent_n,
        design_effect=design_effect,
        expected_analysis_retention=expected_pair_retention,
    )
    return PairedMcNemarPlan(
        pair_n_independent=independent_n,
        cluster_inflated_pair_n=clustered,
        attempted_pair_n=attempted,
        p10=p10,
        p01=p01,
        absolute_risk_difference=abs(p10 - p01),
        discordant_probability=p10 + p01,
        alpha=alpha,
        power=power,
        design_effect=design_effect,
        expected_pair_retention=expected_pair_retention,
    )
