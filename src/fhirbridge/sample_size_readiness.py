"""Readiness and consistency checks for pilot-derived sample-size records."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .sample_size_planning import (
    plan_paired_mcnemar,
    plan_proportion_precision,
)

_EXPECTED_BASE_COMPARISONS = frozenset(
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
_FAMILYWISE_ALPHA = 0.05
_PLANNING_POWER = 0.80


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

    frozen_method = document.get("frozen_method")
    if not isinstance(frozen_method, dict):
        blockers.append("frozen_method is missing")
        frozen_method = {}
    for key in (
        "sample_size_method_sha256",
        "core_confirmatory_design_sha256",
        "model_prompt_configuration_sha256",
    ):
        if _zero_hash(frozen_method.get(key)):
            blockers.append(f"{key} is still a zero placeholder")

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

    model_keys = document.get("model_keys")
    if not isinstance(model_keys, list) or not model_keys:
        blockers.append("model_keys must be a non-empty list")
        model_keys = []
    normalized_model_keys: list[str] = []
    for model_key in model_keys:
        if (
            not isinstance(model_key, str)
            or not model_key
            or _placeholder(model_key)
        ):
            blockers.append("model_keys contain missing or placeholder values")
            continue
        if model_key in normalized_model_keys:
            blockers.append(f"duplicate model_key: {model_key}")
        normalized_model_keys.append(model_key)

    expected_family_size = 6 * len(normalized_model_keys)
    expected_ids = {
        f"{model_key}__{base_id}"
        for model_key in normalized_model_keys
        for base_id in _EXPECTED_BASE_COMPARISONS
    }

    multiplicity = document.get("multiplicity")
    if not isinstance(multiplicity, dict):
        blockers.append("multiplicity is missing")
        multiplicity = {}
    if multiplicity.get("method") != "Holm":
        blockers.append("sample-size multiplicity method is not Holm")
    if not _same_float(
        multiplicity.get("familywise_alpha"),
        _FAMILYWISE_ALPHA,
    ):
        blockers.append("sample-size familywise alpha is not 0.05")
    if multiplicity.get("comparison_family_size") != expected_family_size:
        blockers.append(
            "comparison_family_size must equal six times frozen model count"
        )
    if multiplicity.get("planning_alpha_policy") != (
        "Bonferroni_upper_bound_for_Holm_family"
    ):
        blockers.append("sample-size planning alpha policy is not frozen")
    planning_alpha = (
        _FAMILYWISE_ALPHA / expected_family_size
        if expected_family_size > 0
        else None
    )
    if planning_alpha is not None and not _same_float(
        multiplicity.get("per_comparison_planning_alpha"),
        planning_alpha,
    ):
        blockers.append(
            "per-comparison planning alpha must equal 0.05/(6*model_count)"
        )

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
            blockers.append(
                f"primary precision plan cannot be recomputed: {exc}"
            )
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
    observed_count_by_model = {
        model_key: 0 for model_key in normalized_model_keys
    }
    source_cluster_requirements: list[int] = []
    primary_clusters = primary.get("planned_source_cluster_count")
    if isinstance(primary_clusters, int) and primary_clusters > 0:
        source_cluster_requirements.append(primary_clusters)

    for item in pair_plans:
        if not isinstance(item, dict):
            blockers.append("paired comparison plan is malformed")
            continue
        comparison_id = item.get("comparison_id")
        model_key = item.get("model_key")
        if not isinstance(comparison_id, str) or not comparison_id:
            blockers.append("paired comparison plan lacks comparison_id")
            continue
        if not isinstance(model_key, str) or not model_key:
            blockers.append(f"{comparison_id}: paired plan lacks model_key")
            continue
        if comparison_id in observed_ids:
            blockers.append(f"duplicate paired comparison_id: {comparison_id}")
        observed_ids.add(comparison_id)
        if model_key not in normalized_model_keys:
            blockers.append(
                f"{comparison_id}: model_key is not in frozen model_keys"
            )
        else:
            observed_count_by_model[model_key] += 1
        if not comparison_id.startswith(f"{model_key}__"):
            blockers.append(
                f"{comparison_id}: comparison_id must be prefixed by model_key"
            )

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
        if planning_alpha is not None and not _same_float(
            alpha,
            planning_alpha,
        ):
            blockers.append(
                f"{comparison_id}: planning alpha must equal 0.05/(6*model_count)"
            )
        if not _same_float(power, _PLANNING_POWER):
            blockers.append(
                f"{comparison_id}: planning power must equal 0.80"
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
        if not _same_float(
            item.get("design_effect"),
            recomputed.design_effect,
        ):
            blockers.append(
                f"{comparison_id}.design_effect does not match deterministic "
                "recomputation"
            )
        source_cluster_requirements.append(
            recomputed.planned_source_cluster_count
        )

    if observed_ids != expected_ids:
        blockers.append(
            "paired comparison plans must cover exactly six contrasts for "
            "every frozen model"
        )
    if len(pair_plans) != expected_family_size:
        blockers.append(
            "paired comparison plan count must equal six times frozen model count"
        )
    for model_key, count in observed_count_by_model.items():
        if count != 6:
            blockers.append(
                f"{model_key}: exactly six paired plans are required"
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
                "final_source_cluster_count_recorded_before_confirmatory_inference"
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
