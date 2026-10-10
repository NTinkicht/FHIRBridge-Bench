"""Cross-file consistency checks for the frozen confirmatory design."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXPECTED_STRATEGIES = (
    "direct_structured_llm",
    "mapping_aware_llm",
    "mapping_aware_plus_syntax_repair",
)


@dataclass(frozen=True)
class AnalysisDesignConsistency:
    consistent: bool
    blockers: tuple[str, ...]


def _comparison_signature(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("comparison_id")),
        str(item.get("arm_a")),
        str(item.get("arm_b")),
    )


def assess_analysis_design_consistency(
    core_design: dict[str, Any],
    preregistration_template: dict[str, Any],
    sample_size_method: dict[str, Any],
    execution_policy: dict[str, Any],
) -> AnalysisDesignConsistency:
    blockers: list[str] = []

    design = core_design.get("analysis_design")
    if not isinstance(design, dict):
        return AnalysisDesignConsistency(
            consistent=False,
            blockers=("analysis_design is missing",),
        )

    if design.get("primary_direction") != "FHIR_to_HL7v2":
        blockers.append("core primary direction is not FHIR_to_HL7v2")

    core_arms = design.get("core_arms")
    if not isinstance(core_arms, list):
        blockers.append("core_arms are missing")
        core_arm_ids: list[str] = []
    else:
        core_arm_ids = [
            str(item.get("arm_id"))
            for item in core_arms
            if isinstance(item, dict)
        ]
    expected_arms = ["deterministic_baseline", *_EXPECTED_STRATEGIES]
    if core_arm_ids != expected_arms:
        blockers.append("core arm order/identity does not match frozen design")

    paired = design.get("paired_secondary_comparison_family")
    if not isinstance(paired, dict):
        blockers.append("paired_secondary_comparison_family is missing")
        base_comparisons: list[dict[str, Any]] = []
    else:
        if paired.get("multiplicity_method") != "Holm":
            blockers.append("core multiplicity method is not Holm")
        base_comparisons = paired.get("base_comparisons", [])
        if not isinstance(base_comparisons, list):
            blockers.append("base_comparisons must be a list")
            base_comparisons = []

    core_signatures = {
        _comparison_signature(item)
        for item in base_comparisons
        if isinstance(item, dict)
    }
    if len(core_signatures) != 6:
        blockers.append("core design must define exactly six base comparisons")

    template_paired = preregistration_template.get("paired_comparisons")
    if not isinstance(template_paired, dict):
        blockers.append("analysis preregistration paired_comparisons are missing")
        template_family: list[dict[str, Any]] = []
    else:
        if template_paired.get("cluster_id_field") != design.get(
            "paired_analysis", {}
        ).get("cluster_id_field"):
            blockers.append("analysis template cluster_id_field drifts from core design")
        if template_paired.get("analysis_set_rule") != design.get(
            "paired_analysis", {}
        ).get("VUR_analysis_set_rule"):
            blockers.append("analysis template VUR set rule drifts from core design")
        template_family = template_paired.get("comparison_family", [])
        if not isinstance(template_family, list):
            blockers.append("analysis template comparison_family must be a list")
            template_family = []

    template_signatures: set[tuple[str, str, str]] = set()
    for item in template_family:
        if not isinstance(item, dict):
            continue
        comparison_id = str(item.get("comparison_id", ""))
        model_key = str(item.get("model_key", ""))
        prefix = f"{model_key}__"
        base_id = (
            comparison_id[len(prefix):]
            if model_key and comparison_id.startswith(prefix)
            else comparison_id
        )
        template_signatures.add(
            (
                base_id,
                str(item.get("arm_a")),
                str(item.get("arm_b")),
            )
        )
    if template_signatures != core_signatures:
        blockers.append(
            "analysis preregistration comparison family drifts from core design"
        )

    multiplicity = preregistration_template.get("multiplicity")
    if not isinstance(multiplicity, dict):
        blockers.append("analysis preregistration multiplicity is missing")
    else:
        if multiplicity.get("secondary_pairwise_method") != "Holm":
            blockers.append("analysis preregistration multiplicity is not Holm")
        if multiplicity.get("comparison_family_size") != len(template_family):
            blockers.append(
                "analysis preregistration family size does not match template rows"
            )

    paired_analysis = design.get("paired_analysis")
    if not isinstance(paired_analysis, dict):
        blockers.append("core paired_analysis is missing")
        paired_analysis = {}

    core_bootstrap = paired_analysis.get("bootstrap")
    template_bootstrap = preregistration_template.get("bootstrap")
    if core_bootstrap != template_bootstrap:
        blockers.append("bootstrap configuration drifts between core and template")

    core_mcnemar = paired_analysis.get("mcnemar")
    template_mcnemar = preregistration_template.get("mcnemar")
    if core_mcnemar != template_mcnemar:
        blockers.append("McNemar configuration drifts between core and template")

    companion = preregistration_template.get("companion_estimand")
    if companion != design.get("companion_estimand"):
        blockers.append("VFY companion estimand drifts from core design")

    method = sample_size_method.get("sample_size_method")
    if not isinstance(method, dict):
        blockers.append("sample_size_method is missing")
    else:
        secondary = method.get("paired_secondary_planning")
        if not isinstance(secondary, dict):
            blockers.append("paired sample-size planning policy is missing")
        else:
            if secondary.get("multiplicity_test_method") != "Holm":
                blockers.append("sample-size multiplicity method is not Holm")
            if secondary.get("confirmatory_test") != (
                "two_sided_exact_binomial_McNemar"
            ):
                blockers.append(
                    "sample-size confirmatory test drifts from exact McNemar"
                )

    execution = execution_policy.get("generation_attempt")
    if not isinstance(execution, dict):
        blockers.append("model generation_attempt policy is missing")
    else:
        calls = execution.get("provider_generation_calls_per_case_model")
        expected_calls = {
            "direct_structured_llm": 1,
            "mapping_aware_llm": 1,
            "mapping_aware_plus_syntax_repair": 0,
        }
        if calls != expected_calls:
            blockers.append(
                "provider call counts drift from the frozen three-strategy design"
            )
        if execution.get("repair_arm_source_strategy") != "mapping_aware_llm":
            blockers.append("repair arm source is not mapping_aware_llm")
        if execution.get("repair_arm_same_raw_response_required") is not True:
            blockers.append("repair arm does not require the same raw response")

    return AnalysisDesignConsistency(
        consistent=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
