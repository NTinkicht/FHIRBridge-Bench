"""Readiness and consistency checks for pilot-derived sample-size records."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .sample_size_planning import (
    plan_paired_mcnemar,
    plan_proportion_precision,
)

_EXPECTED_COMPARISONS = frozenset(
    {
        "BASELINE_vs_DIRECT",
        "BASELINE_vs_MAPPING",
        "BASELINE_vs_REPAIR",
        "DIRECT_vs_MAPPING",
        "DIRECT_vs_REPAIR",
        "MAPPING_vs_REPAIR",
    }
)
_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")
_PLANNING_ALPHA = 0.05 / 6.0


@dataclass(frozen=True)
class SampleSizeReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zero_hash(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value.lower()) <= {"0"}
    )


def _same_float(left: Any, right: float) -> bool:
    return isinstance(left, (int, float)) and math.isclose(
        float(left),
        float(right),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def assess_sample_size_preregistration(
    document: dict[str, Any],
) -> SampleSizeReadiness:
    blockers: list[str] = []

    if document.get("status") != "preregistered":
        blockers.append("sample-size record is not marked preregistered")
    if document.get("created_at") is None:
        blockers.append("sample-size record has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened at sample-size freeze")
    if _placeholder(document.get("record_id")):
        blockers.append("sample-size record_id is still a placeholder")

    pilot = document.get("pilot_evidence")
    if not isinstance(pilot, dict):
        blockers.append("pilot_evidence is missing")
        pilot = {}
    for key in ("pilot_case_manifest_sha256", "pilot_analysis_sha256"):
        if _zero_hash(pilot.get(key)):
            blockers.append(f"{key} is still a zero placeholder")

    expected_vur = pilot.get("expected_vur")
    retention = pilot.get("valid_determinate_retention")
    mean_cluster_size = pilot.get("mean_cluster_size")
    icc = pilot.get("icc")
    if not isinstance(expected_vur, (int, float)) or not 0 <= expected_vur <= 1:
        blockers.append("expected_vur must be numeric in [0,1]")
    if not isinstance(retention, (int, float)) or not 0 < retention <= 1:
        blockers.append("valid_determinate_retention must be in (0,1]")
    if (
        not isinstance(mean_cluster_size, (int, float))
        or mean_cluster_size < 1
    ):
        blockers.append("mean_cluster_size must be >= 1")
    if not isinstance(icc, (int, float)) or not 0 <= icc <= 1:
        blockers.append("icc must be numeric in [0,1]")

    primary = document.get("primary_precision_plan")
    if not isinstance(primary, dict):
        blockers.append("primary_precision_plan is missing")
        primary = {}
    target_half_width = primary.get("target_half_width")
    confidence_level = primary.get("confidence_level")
    if (
        isinstance(expected_vur, (int, float))
        and isinstance(retention, (int, float))
        and isinstance(mean_cluster_size, (int, float))
        and isinstance(icc, (int, float))
        and isinstance(target_half_width, (int, float))
        and isinstance(confidence_level, (int, float))
        and 0 <= expected_vur <= 1
        and 0 < retention <= 1
        and mean_cluster_size >= 1
        and 0 <= icc <= 1
        and 0 < target_half_width < 1
    ):
        try:
            recomputed_primary = plan_proportion_precision(
                expected_rate=float(expected_vur),
                target_half_width=float(target_half_width),
                mean_cluster_size=float(mean_cluster_size),
                icc=float(icc),
                expected_analysis_retention=float(retention),
                confidence_level=float(confidence_level),
            )
        except ValueError as exc:
            blockers.append(f"primary precision plan cannot be recomputed: {exc}")
        else:
            expected_values = {
                "independent_row_n": recomputed_primary.independent_row_n,
                "cluster_inflated_row_n": (
                    recomputed_primary.cluster_inflated_row_n
                ),
                "attempted_row_n": recomputed_primary.attempted_row_n,
                "planned_source_cluster_count": (
                    recomputed_primary.planned_source_cluster_count
                ),
            }
            for key, expected in expected_values.items():
                if primary.get(key) != expected:
                    blockers.append(
                        f"primary_precision_plan.{key} does not match "
                        "deterministic recomputation"
                    )
            if not _same_float(
                primary.get("design_effect"),
                recomputed_primary.design_effect,
            ):
                blockers.append(
                    "primary_precision_plan.design_effect does not match "
                    "deterministic recomputation"
                )

    pair_plans = document.get("paired_comparison_plans")
    if not isinstance(pair_plans, list):
        blockers.append("paired_comparison_plans must be a list")
        pair_plans = []

    observed_ids: set[str] = set()
    source_cluster_requirements: list[int] = []
    primary_clusters = primary.get("planned_source_cluster_count")
    if isinstance(primary_clusters, int) and primary_clusters > 0:
        source_cluster_requirements.append(primary_clusters)

    for item in pair_plans:
        if not isinstance(item, dict):
            blockers.append("paired comparison plan is malformed")
            continue
        comparison_id = item.get("comparison_id")
        if not isinstance(comparison_id, str) or not comparison_id:
            blockers.append("paired comparison plan lacks comparison_id")
            continue
        if comparison_id in observed_ids:
            blockers.append(f"duplicate paired comparison_id: {comparison_id}")
        observed_ids.add(comparison_id)

        p10 = item.get("p10")
        p01 = item.get("p01")
        alpha = item.get("alpha")
        power = item.get("power")
        pair_retention = item.get("expected_pair_retention")
        if not all(
            isinstance(value, (int, float))
            for value in (p10, p01, alpha, power, pair_retention)
        ):
            blockers.append(
                f"{comparison_id}: planning probabilities/parameters are incomplete"
            )
            continue
        if not math.isclose(
            float(alpha),
            _PLANNING_ALPHA,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            blockers.append(
                f"{comparison_id}: planning alpha must equal 0.05/6 for the "
                "six-comparison Holm family"
            )
        try:
            recomputed = plan_paired_mcnemar(
                p10=float(p10),
                p01=float(p01),
                mean_cluster_size=float(mean_cluster_size),
                icc=float(icc),
                expected_pair_retention=float(pair_retention),
                alpha=float(alpha),
                power=float(power),
            )
        except (TypeError, ValueError) as exc:
            blockers.append(f"{comparison_id}: cannot recompute plan: {exc}")
            continue

        expected_values = {
            "independent_pair_row_n": recomputed.independent_pair_row_n,
            "cluster_inflated_pair_row_n": (
                recomputed.cluster_inflated_pair_row_n
            ),
            "attempted_pair_row_n": recomputed.attempted_pair_row_n,
            "planned_source_cluster_count": (
                recomputed.planned_source_cluster_count
            ),
        }
        for key, expected in expected_values.items():
            if item.get(key) != expected:
                blockers.append(
                    f"{comparison_id}.{key} does not match deterministic "
                    "recomputation"
                )
        if not _same_float(item.get("design_effect"), recomputed.design_effect):
            blockers.append(
                f"{comparison_id}.design_effect does not match deterministic "
                "recomputation"
            )
        source_cluster_requirements.append(
            recomputed.planned_source_cluster_count
        )

    if observed_ids != _EXPECTED_COMPARISONS:
        blockers.append(
            "paired comparison plans must cover exactly the six predeclared "
            "strategy comparisons"
        )

    final_count = document.get("final_source_cluster_count")
    if source_cluster_requirements:
        required_final = max(source_cluster_requirements)
        if final_count != required_final:
            blockers.append(
                "final_source_cluster_count is not the maximum deterministic "
                "source-cluster requirement"
            )
    elif not isinstance(final_count, int) or final_count < 1:
        blockers.append("final_source_cluster_count must be positive")

    if document.get("selection_rule") != (
        "maximum_required_source_cluster_count_across_primary_precision_and_"
        "all_predeclared_paired_comparisons"
    ):
        blockers.append("sample-size selection_rule is not frozen")

    attestation = document.get("attestation")
    if not isinstance(attestation, dict):
        blockers.append("sample-size attestation is missing")
    else:
        if attestation.get("pilot_only_used_for_planning") is not True:
            blockers.append("sample-size planning is not attested pilot-only")
        if attestation.get("sealed_results_used_for_planning") is not False:
            blockers.append("sealed results must not be used for sample sizing")
        if (
            attestation.get(
                "final_case_count_recorded_before_confirmatory_inference"
            )
            is not True
        ):
            blockers.append(
                "final sample size is not attested as pre-confirmatory"
            )

    return SampleSizeReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
