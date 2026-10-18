from copy import deepcopy

import yaml

from fhirbridge.sample_size_planning import (
    plan_paired_mcnemar,
    plan_proportion_precision,
)
from fhirbridge.sample_size_readiness import (
    assess_sample_size_preregistration,
)

_TEMPLATE = "analysis/examples/sample_size_preregistration_template.yaml"
_BASE_COMPARISONS = (
    "BASELINE_vs_DIRECT",
    "BASELINE_vs_MAPPING",
    "BASELINE_vs_REPAIR",
    "DIRECT_vs_MAPPING",
    "DIRECT_vs_REPAIR",
    "MAPPING_vs_REPAIR",
)


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _ready(model_keys: tuple[str, ...] = ("MODEL-A",)) -> dict:
    record = _template()
    record["record_id"] = "SAMPLE-SIZE-001"
    record["status"] = "preregistered"
    record["created_at"] = "2026-10-20T14:00:00Z"
    record["frozen_method"].update(
        {
            "sample_size_method_sha256": "a" * 64,
            "core_confirmatory_design_sha256": "b" * 64,
            "model_prompt_configuration_sha256": "c" * 64,
        }
    )
    record["pilot_evidence"].update(
        {
            "pilot_case_manifest_sha256": "1" * 64,
            "pilot_analysis_sha256": "2" * 64,
            "expected_vur": 0.20,
            "valid_determinate_retention": 0.80,
            "mean_cluster_size": 2.0,
            "icc": 0.10,
        }
    )
    record["model_keys"] = list(model_keys)
    family_size = 6 * len(model_keys)
    alpha = 0.05 / family_size
    record["multiplicity"] = {
        "method": "Holm",
        "familywise_alpha": 0.05,
        "comparison_family_size": family_size,
        "planning_alpha_policy": "Bonferroni_upper_bound_for_Holm_family",
        "per_comparison_planning_alpha": alpha,
    }

    primary = plan_proportion_precision(
        expected_rate=0.20,
        target_half_width=0.05,
        mean_cluster_size=2.0,
        icc=0.10,
        expected_analysis_retention=0.80,
        confidence_level=0.95,
    )
    record["primary_precision_plan"] = {
        "confidence_level": 0.95,
        "target_half_width": 0.05,
        "independent_row_n": primary.independent_row_n,
        "design_effect": primary.design_effect,
        "cluster_inflated_row_n": primary.cluster_inflated_row_n,
        "attempted_row_n": primary.attempted_row_n,
        "planned_source_cluster_count": (
            primary.planned_source_cluster_count
        ),
    }

    pair_records = []
    row_index = 0
    for model_key in model_keys:
        for base_id in _BASE_COMPARISONS:
            p10 = 0.16 + row_index * 0.002
            p01 = 0.05
            plan = plan_paired_mcnemar(
                p10=p10,
                p01=p01,
                mean_cluster_size=2.0,
                icc=0.10,
                expected_pair_retention=0.75,
                alpha=alpha,
                power=0.80,
            )
            pair_records.append(
                {
                    "comparison_id": f"{model_key}__{base_id}",
                    "model_key": model_key,
                    "p10": p10,
                    "p01": p01,
                    "alpha": alpha,
                    "power": 0.80,
                    "expected_pair_retention": 0.75,
                    "independent_pair_row_n": plan.independent_pair_row_n,
                    "design_effect": plan.design_effect,
                    "cluster_inflated_pair_row_n": (
                        plan.cluster_inflated_pair_row_n
                    ),
                    "attempted_pair_row_n": plan.attempted_pair_row_n,
                    "planned_source_cluster_count": (
                        plan.planned_source_cluster_count
                    ),
                    "planning_method": plan.method,
                }
            )
            row_index += 1
    record["paired_comparison_plans"] = pair_records
    record["final_source_cluster_count"] = max(
        [
            primary.planned_source_cluster_count,
            *[
                item["planned_source_cluster_count"]
                for item in pair_records
            ],
        ]
    )
    return record


def test_repository_sample_size_template_is_deliberately_not_ready() -> None:
    readiness = assess_sample_size_preregistration(_template())

    assert not readiness.ready
    assert any("not marked preregistered" in item for item in readiness.blockers)
    assert any("zero placeholder" in item for item in readiness.blockers)
    assert any("model_keys" in item for item in readiness.blockers)


def test_deterministically_recomputed_sample_size_record_can_be_ready() -> None:
    readiness = assess_sample_size_preregistration(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_two_model_family_requires_twelve_plans_and_dynamic_alpha() -> None:
    record = _ready(("MODEL-A", "MODEL-B"))
    readiness = assess_sample_size_preregistration(record)

    assert readiness.ready
    assert len(record["paired_comparison_plans"]) == 12
    assert record["multiplicity"]["comparison_family_size"] == 12
    assert record["multiplicity"]["per_comparison_planning_alpha"] == (
        0.05 / 12
    )


def test_tampered_primary_plan_is_rejected() -> None:
    record = _ready()
    record["primary_precision_plan"]["attempted_row_n"] += 1

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "attempted_row_n does not match deterministic recomputation" in item
        for item in readiness.blockers
    )


def test_final_source_cluster_count_must_equal_maximum_requirement() -> None:
    record = _ready()
    record["final_source_cluster_count"] += 1

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "not the maximum deterministic source-cluster requirement" in item
        for item in readiness.blockers
    )


def test_duplicate_or_missing_comparison_ids_are_rejected() -> None:
    record = _ready()
    record["paired_comparison_plans"][1]["comparison_id"] = (
        record["paired_comparison_plans"][0]["comparison_id"]
    )

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "duplicate paired comparison_id" in item for item in readiness.blockers
    )
    assert any(
        "six contrasts for every frozen model" in item
        for item in readiness.blockers
    )


def test_planning_alpha_must_cover_full_model_specific_holm_family() -> None:
    record = _ready(("MODEL-A", "MODEL-B"))
    record["paired_comparison_plans"][0]["alpha"] = 0.05 / 6.0

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "planning alpha must equal 0.05/(6*model_count)" in item
        for item in readiness.blockers
    )


def test_multiplicity_family_size_must_match_frozen_model_count() -> None:
    record = _ready(("MODEL-A", "MODEL-B"))
    record["multiplicity"]["comparison_family_size"] = 6

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "six times frozen model count" in item
        for item in readiness.blockers
    )


def test_sealed_results_can_never_be_used_for_sample_sizing() -> None:
    record = _ready()
    record["attestation"]["sealed_results_used_for_planning"] = True

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any("sealed results" in item for item in readiness.blockers)


def test_zero_pilot_hash_blocks_sample_size_freeze() -> None:
    record = deepcopy(_ready())
    record["pilot_evidence"]["pilot_analysis_sha256"] = "0" * 64

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any("pilot_analysis_sha256" in item for item in readiness.blockers)


def test_zero_method_hash_blocks_sample_size_freeze() -> None:
    record = deepcopy(_ready())
    record["frozen_method"]["sample_size_method_sha256"] = "0" * 64

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "sample_size_method_sha256" in item
        for item in readiness.blockers
    )


def test_zero_model_config_hash_blocks_sample_size_freeze() -> None:
    record = deepcopy(_ready())
    record["frozen_method"]["model_prompt_configuration_sha256"] = "0" * 64

    readiness = assess_sample_size_preregistration(record)

    assert not readiness.ready
    assert any(
        "model_prompt_configuration_sha256" in item
        for item in readiness.blockers
    )
