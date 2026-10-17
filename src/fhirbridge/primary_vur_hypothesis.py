"""Readiness checks for the pilot-derived primary VUR hypothesis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class PrimaryVurHypothesisReadiness:
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


def assess_primary_vur_hypothesis(
    document: dict[str, Any],
) -> PrimaryVurHypothesisReadiness:
    blockers: list[str] = []

    if document.get("status") != "preregistered":
        blockers.append("primary VUR hypothesis is not marked preregistered")
    if document.get("created_at") is None:
        blockers.append("primary VUR hypothesis has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened at hypothesis freeze")
    if _placeholder(document.get("record_id")):
        blockers.append("primary VUR hypothesis record_id is still a placeholder")

    pilot = document.get("pilot_evidence")
    if not isinstance(pilot, dict):
        blockers.append("pilot_evidence is missing")
        pilot = {}
    for key in ("pilot_case_manifest_sha256", "pilot_analysis_sha256"):
        if _zero_hash(pilot.get(key)):
            blockers.append(f"{key} is still a zero placeholder")

    hypothesis = document.get("hypothesis")
    if not isinstance(hypothesis, dict):
        blockers.append("hypothesis is missing")
        hypothesis = {}
    threshold = hypothesis.get("nontrivial_vur_threshold")
    if (
        not isinstance(threshold, (int, float))
        or not 0 < float(threshold) < 1
    ):
        blockers.append("nontrivial VUR threshold must be numeric in (0,1)")
    rationale = hypothesis.get("threshold_rationale")
    if (
        not isinstance(rationale, str)
        or not rationale.strip()
        or _placeholder(rationale)
    ):
        blockers.append("threshold rationale is missing or still a placeholder")

    population = document.get("target_population")
    if not isinstance(population, dict):
        blockers.append("target_population is missing")
        population = {}
    for key in ("inclusion_rule", "model_strategy_aggregation_policy"):
        value = population.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
            or _placeholder(value)
        ):
            blockers.append(f"{key} is missing or still a placeholder")
    if population.get("cluster_id_field") != "analysis_cluster_id":
        blockers.append("cluster_id_field is not frozen to analysis_cluster_id")

    inference = document.get("inference")
    if not isinstance(inference, dict):
        blockers.append("inference is missing")
        inference = {}
    for key in (
        "method",
        "cluster_handling",
        "confidence_interval_method",
        "decision_rule",
    ):
        value = inference.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
            or _placeholder(value)
        ):
            blockers.append(f"inference.{key} is missing or still a placeholder")
    if inference.get("alpha") != 0.05:
        blockers.append("primary hypothesis alpha is not frozen to 0.05")
    if inference.get("sidedness") != "one_sided":
        blockers.append("primary hypothesis sidedness is not one_sided")

    estimand = document.get("estimand")
    if not isinstance(estimand, dict):
        blockers.append("estimand is missing")
    else:
        if estimand.get("name") != "VUR":
            blockers.append("primary hypothesis estimand is not VUR")
        if estimand.get("direction") != "FHIR_to_HL7v2":
            blockers.append("primary hypothesis direction is not FHIR_to_HL7v2")
        if estimand.get("denominator_rule") != (
            "VALID_and_semantic_determinate"
        ):
            blockers.append("primary VUR denominator rule has drifted")

    indeterminate = document.get("indeterminate_policy")
    if not isinstance(indeterminate, dict):
        blockers.append("indeterminate_policy is missing")
    else:
        if indeterminate.get("semantic_indeterminate_policy") != (
            "exclude_from_binary_VUR_with_reported_denominator_loss_and_"
            "sensitivity_bounds"
        ):
            blockers.append("semantic indeterminate policy has drifted")
        if indeterminate.get("structural_policy_ref") != (
            "benchmark/structural_validity_policy.yaml"
        ):
            blockers.append("structural validity policy reference has drifted")

    return PrimaryVurHypothesisReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
