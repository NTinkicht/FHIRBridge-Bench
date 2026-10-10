from copy import deepcopy

import yaml

from fhirbridge.analysis_design_consistency import (
    assess_analysis_design_consistency,
)

_CORE = "analysis/core_confirmatory_design.yaml"
_TEMPLATE = "analysis/examples/analysis_preregistration_template.yaml"
_SAMPLE = "analysis/sample_size_method.yaml"
_EXECUTION = "models/execution_policy.yaml"


def _yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _documents() -> tuple[dict, dict, dict, dict]:
    return (
        _yaml(_CORE),
        _yaml(_TEMPLATE),
        _yaml(_SAMPLE),
        _yaml(_EXECUTION),
    )


def test_repository_confirmatory_design_documents_are_consistent() -> None:
    result = assess_analysis_design_consistency(*_documents())

    assert result.consistent
    assert result.blockers == ()


def test_analysis_template_comparison_family_cannot_drift() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(template)
    mutated["paired_comparisons"]["comparison_family"][0]["arm_b"] = (
        "mapping_aware_llm"
    )

    result = assess_analysis_design_consistency(
        core,
        mutated,
        sample,
        execution,
    )

    assert not result.consistent
    assert any("comparison family drifts" in item for item in result.blockers)


def test_bootstrap_seed_cannot_drift_between_core_and_template() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(template)
    mutated["bootstrap"]["seed"] += 1

    result = assess_analysis_design_consistency(
        core,
        mutated,
        sample,
        execution,
    )

    assert not result.consistent
    assert any("bootstrap configuration drifts" in item for item in result.blockers)


def test_sample_size_confirmatory_test_must_remain_exact_mcnemar() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(sample)
    mutated["sample_size_method"]["paired_secondary_planning"][
        "confirmatory_test"
    ] = "asymptotic_McNemar"

    result = assess_analysis_design_consistency(
        core,
        template,
        mutated,
        execution,
    )

    assert not result.consistent
    assert any("exact McNemar" in item for item in result.blockers)


def test_repair_arm_cannot_gain_independent_provider_call() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(execution)
    mutated["generation_attempt"]["provider_generation_calls_per_case_model"][
        "mapping_aware_plus_syntax_repair"
    ] = 1

    result = assess_analysis_design_consistency(
        core,
        template,
        sample,
        mutated,
    )

    assert not result.consistent
    assert any("provider call counts drift" in item for item in result.blockers)


def test_repair_arm_must_reuse_mapping_raw_response() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(execution)
    mutated["generation_attempt"]["repair_arm_same_raw_response_required"] = False

    result = assess_analysis_design_consistency(
        core,
        template,
        sample,
        mutated,
    )

    assert not result.consistent
    assert any("same raw response" in item for item in result.blockers)


def test_sample_size_family_size_rule_must_follow_frozen_model_count() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(sample)
    mutated["sample_size_method"]["paired_secondary_planning"][
        "family_size_rule"
    ] = "six_strategy_contrasts_total"

    result = assess_analysis_design_consistency(
        core,
        template,
        mutated,
        execution,
    )

    assert not result.consistent
    assert any(
        "six contrasts per model" in item for item in result.blockers
    )


def test_sample_size_method_cannot_freeze_static_per_comparison_alpha() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(sample)
    mutated["sample_size_method"]["paired_secondary_planning"][
        "per_comparison_planning_alpha"
    ] = 0.05 / 6.0

    result = assess_analysis_design_consistency(
        core,
        template,
        mutated,
        execution,
    )

    assert not result.consistent
    assert any(
        "must not freeze a static per-comparison alpha" in item
        for item in result.blockers
    )


def test_sample_size_dynamic_planning_policy_cannot_drift() -> None:
    core, template, sample, execution = _documents()
    mutated = deepcopy(sample)
    mutated["sample_size_method"]["paired_secondary_planning"][
        "planning_alpha_policy"
    ] = "Bonferroni_upper_bound_for_Holm_family_static_6"

    result = assess_analysis_design_consistency(
        core,
        template,
        mutated,
        execution,
    )

    assert not result.consistent
    assert any(
        "dynamic 0.05/(6M)" in item for item in result.blockers
    )
