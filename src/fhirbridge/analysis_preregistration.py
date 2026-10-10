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
    ):
        if _zeroish(frozen.get(key)):
            blockers.append(f"{key} is still a zero placeholder")

    comparisons = document.get("paired_comparisons")
    if not isinstance(comparisons, dict):
        blockers.append("paired_comparisons are missing")
        comparisons = {}
    cluster_id_field = comparisons.get("cluster_id_field")
    if not isinstance(cluster_id_field, str) or not cluster_id_field.strip():
        blockers.append("cluster_id_field is missing")

    family = comparisons.get("comparison_family")
    if not isinstance(family, list) or not family:
        blockers.append("comparison_family is empty")
        family = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for item in family:
        if not isinstance(item, dict):
            blockers.append("comparison_family contains malformed item")
            continue
        comparison_id = item.get("comparison_id")
        arm_a = item.get("arm_a")
        arm_b = item.get("arm_b")
        if any(_placeholder(value) for value in (comparison_id, arm_a, arm_b)):
            blockers.append("comparison_family contains placeholder values")
        if not all(isinstance(value, str) and value for value in (comparison_id, arm_a, arm_b)):
            blockers.append("comparison_family requires non-empty string IDs")
            continue
        if comparison_id in seen_ids:
            blockers.append(f"duplicate comparison_id: {comparison_id}")
        seen_ids.add(comparison_id)
        if arm_a == arm_b:
            blockers.append(f"{comparison_id}: comparison arms must be distinct")
        normalized_pair = tuple(sorted((arm_a, arm_b)))
        if normalized_pair in seen_pairs:
            blockers.append(
                f"{comparison_id}: duplicate unordered comparison pair"
            )
        seen_pairs.add(normalized_pair)

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
    if not isinstance(multiplicity, dict) or multiplicity.get(
        "secondary_pairwise_method"
    ) != "Holm":
        blockers.append("secondary multiplicity method is not frozen to Holm")

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
