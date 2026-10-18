"""Fail-closed readiness checks for confirmatory analysis preregistration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class AnalysisPreregistrationReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zeroish(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and set(value.lower()) <= {"0"}


def assess_analysis_preregistration(
    document: dict[str, Any],
) -> AnalysisPreregistrationReadiness:
    blockers: list[str] = []

    if document.get("status") != "preregistered":
        blockers.append("analysis record is not marked preregistered")
    if document.get("created_at") is None:
        blockers.append("analysis preregistration has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened at preregistration")
    if _placeholder(document.get("analysis_id")):
        blockers.append("analysis_id is still a placeholder")

    frozen = document.get("frozen_inputs")
    if not isinstance(frozen, dict):
        blockers.append("frozen_inputs are missing")
        frozen = {}
    if _zeroish(frozen.get("repository_commit")):
        blockers.append("repository_commit is still a zero placeholder")
    for key in (
        "projectability_contract_sha256",
        "structural_validity_policy_sha256",
        "statistical_analysis_plan_sha256",
        "model_prompt_configuration_sha256",
        "sample_size_preregistration_sha256",
        "primary_vur_hypothesis_sha256",
    ):
        if _zeroish(frozen.get(key)):
            blockers.append(f"{key} is still a zero placeholder")

    primary_hypothesis = document.get("primary_hypothesis")
    if not isinstance(primary_hypothesis, dict):
        blockers.append("primary_hypothesis is missing")
        primary_hypothesis = {}
    record_id = primary_hypothesis.get("record_id")
    if (
        not isinstance(record_id, str)
        or not record_id.strip()
        or _placeholder(record_id)
    ):
        blockers.append("primary hypothesis record_id is missing or placeholder")
    threshold = primary_hypothesis.get("nontrivial_vur_threshold")
    if (
        not isinstance(threshold, (int, float))
        or not 0 < float(threshold) < 1
    ):
        blockers.append("primary nontrivial VUR threshold must be in (0,1)")
    for key in (
        "model_strategy_aggregation_policy",
        "inference_method",
        "decision_rule",
    ):
        value = primary_hypothesis.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
            or _placeholder(value)
        ):
            blockers.append(
                f"primary_hypothesis.{key} is missing or placeholder"
            )
    if primary_hypothesis.get("alpha") != 0.05:
        blockers.append("primary hypothesis alpha is not 0.05")
    if primary_hypothesis.get("sidedness") != "one_sided":
        blockers.append("primary hypothesis sidedness is not one_sided")
    if primary_hypothesis.get("cluster_id_field") != "analysis_cluster_id":
        blockers.append(
            "primary hypothesis cluster_id_field is not analysis_cluster_id"
        )

    comparisons = document.get("paired_comparisons")
    if not isinstance(comparisons, dict):
        blockers.append("paired_comparisons are missing")
        comparisons = {}
    cluster_id_field = comparisons.get("cluster_id_field")
    if not isinstance(cluster_id_field, str) or not cluster_id_field.strip():
        blockers.append("cluster_id_field is missing")

    model_keys = comparisons.get("model_keys")
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

    family = comparisons.get("comparison_family")
    if not isinstance(family, list) or not family:
        blockers.append("comparison_family is empty")
        family = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str, str]] = set()
    pair_count_by_model: dict[str, int] = {
        model_key: 0 for model_key in normalized_model_keys
    }
    for item in family:
        if not isinstance(item, dict):
            blockers.append("comparison_family contains malformed item")
            continue
        comparison_id = item.get("comparison_id")
        model_key = item.get("model_key")
        arm_a = item.get("arm_a")
        arm_b = item.get("arm_b")
        if any(
            _placeholder(value)
            for value in (comparison_id, model_key, arm_a, arm_b)
        ):
            blockers.append("comparison_family contains placeholder values")
        if not all(
            isinstance(value, str) and value
            for value in (comparison_id, model_key, arm_a, arm_b)
        ):
            blockers.append("comparison_family requires non-empty string IDs")
            continue
        if model_key not in normalized_model_keys:
            blockers.append(
                f"{comparison_id}: model_key is not declared in model_keys"
            )
        if comparison_id in seen_ids:
            blockers.append(f"duplicate comparison_id: {comparison_id}")
        seen_ids.add(comparison_id)
        if not comparison_id.startswith(f"{model_key}__"):
            blockers.append(
                f"{comparison_id}: comparison_id must be prefixed by model_key"
            )
        if arm_a == arm_b:
            blockers.append(f"{comparison_id}: comparison arms must be distinct")
        normalized_pair = (
            model_key,
            *sorted((arm_a, arm_b)),
        )
        if normalized_pair in seen_pairs:
            blockers.append(
                f"{comparison_id}: duplicate unordered comparison pair within model"
            )
        else:
            seen_pairs.add(normalized_pair)
            if model_key in pair_count_by_model:
                pair_count_by_model[model_key] += 1

    for model_key, count in pair_count_by_model.items():
        if count != 6:
            blockers.append(
                f"{model_key}: exactly six model-specific comparisons are required"
            )

    expected_family_size = 6 * len(normalized_model_keys)
    if len(family) != expected_family_size:
        blockers.append(
            "comparison_family size must equal six times the frozen model count"
        )


    bootstrap = document.get("bootstrap")
    if not isinstance(bootstrap, dict):
        blockers.append("bootstrap definition is missing")
    else:
        if bootstrap.get("iterations") != 10000:
            blockers.append("bootstrap iterations must equal 10000")
        seed = bootstrap.get("seed")
        if not isinstance(seed, int) or seed < 0:
            blockers.append("bootstrap seed must be a nonnegative integer")
        elif seed == 0:
            blockers.append("bootstrap seed is still the template placeholder")

    multiplicity = document.get("multiplicity")
    if not isinstance(multiplicity, dict):
        blockers.append("multiplicity definition is missing")
    else:
        if multiplicity.get("secondary_pairwise_method") != "Holm":
            blockers.append(
                "secondary multiplicity method is not frozen to Holm"
            )
        if multiplicity.get("comparison_family_size") != len(family):
            blockers.append(
                "multiplicity comparison_family_size does not match family"
            )

    mcnemar = document.get("mcnemar")
    if not isinstance(mcnemar, dict):
        blockers.append("McNemar definition is missing")
    elif (
        mcnemar.get("method") != "exact_binomial"
        or mcnemar.get("sidedness") != "two_sided"
    ):
        blockers.append("McNemar test is not frozen to two-sided exact binomial")

    return AnalysisPreregistrationReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
