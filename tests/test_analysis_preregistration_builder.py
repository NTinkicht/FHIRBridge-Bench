import importlib.util
import json
from pathlib import Path

import jsonschema
import yaml

from fhirbridge.sample_size_planning import (
    plan_paired_mcnemar,
    plan_proportion_precision,
)

_MODULE_PATH = Path("analysis/build_analysis_preregistration.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_analysis_preregistration",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_SCHEMA = Path("analysis/schema/analysis_preregistration.schema.json")
_MODEL_TEMPLATE = Path("models/examples/model_prompt_freeze_template.yaml")
_SAMPLE_TEMPLATE = Path(
    "analysis/examples/sample_size_preregistration_template.yaml"
)
_CORE = Path("analysis/core_confirmatory_design.yaml")

_COMPARISONS = (
    "BASELINE_vs_DIRECT",
    "BASELINE_vs_MAPPING",
    "BASELINE_vs_REPAIR",
    "DIRECT_vs_MAPPING",
    "DIRECT_vs_REPAIR",
    "MAPPING_vs_REPAIR",
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _artifact(character: str) -> dict:
    return {
        "path_or_ref": f"frozen/{character}.txt",
        "sha256": character * 64,
    }


def _model(key: str) -> dict:
    return {
        "model_key": key,
        "provider": "provider-x",
        "model_id": f"model-{key}",
        "model_revision_or_snapshot": f"snapshot-{key}",
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 4096,
        "seed_policy": "fixed_supported_seed",
        "seed": 20261020,
        "structured_output_mode": "json_schema",
    }


def _ready_model_config() -> dict:
    document = _yaml(_MODEL_TEMPLATE)
    document["config_id"] = "MODEL-FREEZE-001"
    document["status"] = "frozen"
    document["created_at"] = "2026-10-20T13:00:00Z"
    document["global_execution_policy"]["policy_artifact"] = {
        "path_or_ref": "models/execution_policy.yaml",
        "sha256": "e" * 64,
    }
    document["deterministic_baseline"]["implementation_artifact"] = _artifact(
        "1"
    )
    document["llm_models"] = [_model("M1"), _model("M2")]
    for index, strategy in enumerate(document["llm_strategies"], start=2):
        strategy["implementation_artifact"] = _artifact(str(index))
        if strategy["strategy_id"] == "direct_structured_llm":
            strategy["prompt_artifacts"] = [_artifact("5")]
        else:
            strategy["prompt_artifacts"] = [_artifact("6")]
            strategy["mapping_context_artifacts"] = [_artifact("8")]
        if (
            strategy["strategy_id"]
            == "mapping_aware_plus_syntax_repair"
        ):
            strategy["syntax_repair"]["implementation_artifact"] = _artifact(
                "9"
            )
    return document


def _ready_sample_size() -> dict:
    record = _yaml(_SAMPLE_TEMPLATE)
    record["record_id"] = "SAMPLE-SIZE-001"
    record["status"] = "preregistered"
    record["created_at"] = "2026-10-20T14:00:00Z"
    record["frozen_method"].update(
        {
            "sample_size_method_sha256": "1" * 64,
            "core_confirmatory_design_sha256": "2" * 64,
            "model_prompt_configuration_sha256": "d" * 64,
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
    model_keys = ["M1", "M2"]
    record["model_keys"] = model_keys
    alpha = 0.05 / (6 * len(model_keys))
    record["multiplicity"] = {
        "method": "Holm",
        "familywise_alpha": 0.05,
        "comparison_family_size": 12,
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

    plans = []
    row_index = 0
    for model_key in model_keys:
        for base_id in _COMPARISONS:
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
            plans.append(
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
    record["paired_comparison_plans"] = plans
    record["final_source_cluster_count"] = max(
        primary.planned_source_cluster_count,
        *(item["planned_source_cluster_count"] for item in plans),
    )
    return record


def _ready_primary_hypothesis() -> dict:
    return {
        "schema_version": "0.1.0",
        "record_id": "PRIMARY-VUR-001",
        "status": "preregistered",
        "created_at": "2026-10-20T14:30:00Z",
        "sealed_set_opened": False,
        "pilot_evidence": {
            "pilot_case_manifest_sha256": "a" * 64,
            "pilot_analysis_sha256": "b" * 64,
        },
        "estimand": {
            "name": "VUR",
            "direction": "FHIR_to_HL7v2",
            "denominator_rule": "VALID_and_semantic_determinate",
        },
        "hypothesis": {
            "null_relation": "VUR_less_than_or_equal_threshold",
            "alternative_relation": "VUR_greater_than_threshold",
            "nontrivial_vur_threshold": 0.10,
            "threshold_rationale": "Pilot-derived non-trivial threshold.",
        },
        "target_population": {
            "inclusion_rule": "Frozen eligible FHIR-to-HL7v2 LLM outputs.",
            "model_strategy_aggregation_policy": (
                "Frozen cluster-aware aggregation across model/strategy rows."
            ),
            "cluster_id_field": "analysis_cluster_id",
        },
        "inference": {
            "method": "cluster_aware_one_sided_threshold_test",
            "alpha": 0.05,
            "sidedness": "one_sided",
            "cluster_handling": "Use frozen analysis_cluster_id.",
            "confidence_interval_method": "Frozen cluster-aware interval.",
            "decision_rule": "Reject H0 only at frozen alpha 0.05.",
        },
        "indeterminate_policy": {
            "semantic_indeterminate_policy": (
                "exclude_from_binary_VUR_with_reported_denominator_loss_and_"
                "sensitivity_bounds"
            ),
            "structural_policy_ref": (
                "benchmark/structural_validity_policy.yaml"
            ),
        },
    }


def _hashes() -> dict[str, str]:
    return {
        "projectability_contract_sha256": "a" * 64,
        "structural_validity_policy_sha256": "b" * 64,
        "statistical_analysis_plan_sha256": "c" * 64,
        "model_prompt_configuration_sha256": "d" * 64,
        "sample_size_preregistration_sha256": "e" * 64,
        "primary_vur_hypothesis_sha256": "f" * 64,
    }


def test_expand_comparison_family_creates_six_rows_per_model() -> None:
    core = _yaml(_CORE)
    base = _MODULE._base_comparisons(core)

    family = _MODULE.expand_comparison_family(["M1", "M2"], base)

    assert len(family) == 12
    assert family[0]["comparison_id"] == "M1__BASELINE_vs_DIRECT"
    assert family[5]["comparison_id"] == "M1__MAPPING_vs_REPAIR"
    assert family[6]["comparison_id"] == "M2__BASELINE_vs_DIRECT"
    assert family[-1]["comparison_id"] == "M2__MAPPING_vs_REPAIR"


def test_assembler_builds_schema_valid_ready_analysis_record() -> None:
    record = _MODULE.assemble_analysis_preregistration(
        model_config=_ready_model_config(),
        sample_size=_ready_sample_size(),
        primary_hypothesis=_ready_primary_hypothesis(),
        core_design=_yaml(_CORE),
        repository_commit="abcdef1",
        analysis_id="ANALYSIS-001",
        created_at="2026-10-20T15:00:00Z",
        input_hashes=_hashes(),
    )

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(record)

    assert record["status"] == "preregistered"
    assert record["paired_comparisons"]["model_keys"] == ["M1", "M2"]
    assert len(record["paired_comparisons"]["comparison_family"]) == 12
    assert record["multiplicity"] == {
        "secondary_pairwise_method": "Holm",
        "comparison_family_size": 12,
    }
    assert record["bootstrap"]["iterations"] == 10000
    assert record["bootstrap"]["seed"] == 20261010
    assert record["mcnemar"] == {
        "method": "exact_binomial",
        "sidedness": "two_sided",
        "scope": "model_specific_only",
    }
    assert record["frozen_inputs"]["model_prompt_configuration_sha256"] == (
        "d" * 64
    )


def test_assembler_rejects_incomplete_repository_model_template() -> None:
    try:
        _MODULE.assemble_analysis_preregistration(
            model_config=_yaml(_MODEL_TEMPLATE),
            sample_size=_ready_sample_size(),
            primary_hypothesis=_ready_primary_hypothesis(),
            core_design=_yaml(_CORE),
            repository_commit="abcdef1",
            analysis_id="ANALYSIS-001",
            created_at="2026-10-20T15:00:00Z",
            input_hashes=_hashes(),
        )
    except ValueError as exc:
        assert "model/prompt configuration is not freeze-ready" in str(exc)
    else:
        raise AssertionError("incomplete model template must be rejected")


def test_assembler_rejects_incomplete_sample_size_template() -> None:
    try:
        _MODULE.assemble_analysis_preregistration(
            model_config=_ready_model_config(),
            sample_size=_yaml(_SAMPLE_TEMPLATE),
            core_design=_yaml(_CORE),
            repository_commit="abcdef1",
            analysis_id="ANALYSIS-001",
            created_at="2026-10-20T15:00:00Z",
            input_hashes=_hashes(),
        )
    except ValueError as exc:
        assert "sample-size preregistration is not freeze-ready" in str(exc)
    else:
        raise AssertionError("incomplete sample-size template must be rejected")


def test_assembler_rejects_missing_frozen_input_hash() -> None:
    hashes = _hashes()
    del hashes["statistical_analysis_plan_sha256"]

    try:
        _MODULE.assemble_analysis_preregistration(
            model_config=_ready_model_config(),
            sample_size=_ready_sample_size(),
            primary_hypothesis=_ready_primary_hypothesis(),
            core_design=_yaml(_CORE),
            repository_commit="abcdef1",
            analysis_id="ANALYSIS-001",
            created_at="2026-10-20T15:00:00Z",
            input_hashes=hashes,
        )
    except ValueError as exc:
        assert "input_hashes do not match required frozen inputs" in str(exc)
    else:
        raise AssertionError("missing frozen input hash must be rejected")


def test_assembler_rejects_sample_size_model_key_drift() -> None:
    sample_size = _ready_sample_size()
    sample_size["model_keys"] = ["M1"]

    try:
        _MODULE.assemble_analysis_preregistration(
            model_config=_ready_model_config(),
            sample_size=sample_size,
            primary_hypothesis=_ready_primary_hypothesis(),
            core_design=_yaml(_CORE),
            repository_commit="abcdef1",
            analysis_id="ANALYSIS-001",
            created_at="2026-10-20T15:00:00Z",
            input_hashes=_hashes(),
        )
    except ValueError as exc:
        assert (
            "sample-size preregistration is not freeze-ready" in str(exc)
            or "sample-size model_keys do not match" in str(exc)
        )
    else:
        raise AssertionError("sample-size model-key drift must be rejected")


def test_assembler_rejects_sample_size_model_config_hash_drift() -> None:
    sample_size = _ready_sample_size()
    sample_size["frozen_method"]["model_prompt_configuration_sha256"] = (
        "f" * 64
    )

    try:
        _MODULE.assemble_analysis_preregistration(
            model_config=_ready_model_config(),
            sample_size=sample_size,
            primary_hypothesis=_ready_primary_hypothesis(),
            core_design=_yaml(_CORE),
            repository_commit="abcdef1",
            analysis_id="ANALYSIS-001",
            created_at="2026-10-20T15:00:00Z",
            input_hashes=_hashes(),
        )
    except ValueError as exc:
        assert "same frozen model configuration" in str(exc)
    else:
        raise AssertionError("sample-size model-config hash drift must be rejected")


def test_assembler_rejects_unfrozen_primary_hypothesis() -> None:
    hypothesis = _ready_primary_hypothesis()
    hypothesis["status"] = "incomplete_template"

    try:
        _MODULE.assemble_analysis_preregistration(
            model_config=_ready_model_config(),
            sample_size=_ready_sample_size(),
            primary_hypothesis=hypothesis,
            core_design=_yaml(_CORE),
            repository_commit="abcdef1",
            analysis_id="ANALYSIS-001",
            created_at="2026-10-20T15:00:00Z",
            input_hashes=_hashes(),
        )
    except ValueError as exc:
        assert "primary VUR hypothesis is not freeze-ready" in str(exc)
    else:
        raise AssertionError("unfrozen primary hypothesis must be rejected")
