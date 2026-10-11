from copy import deepcopy

import pytest

from fhirbridge.analysis_dataset import build_analysis_rows


def _sealed() -> dict:
    return {
        "schema_version": "0.1.0",
        "manifest_id": "SEALED-CASES-001",
        "status": "sealed",
        "created_at": "2026-10-20T09:00:00Z",
        "split": "sealed_test",
        "case_count": 2,
        "cases": [
            {
                "case_id": "C1",
                "scenario_family": "LAB-001",
                "analysis_cluster_id": "SOURCE-C1",
                "source_input_sha256": "1" * 64,
                "canonical_graph_sha256": "2" * 64,
            },
            {
                "case_id": "C2",
                "scenario_family": "LAB-006",
                "analysis_cluster_id": "SOURCE-C2",
                "source_input_sha256": "3" * 64,
                "canonical_graph_sha256": "4" * 64,
            },
        ],
    }


def _key_records() -> tuple[list[dict], list[dict]]:
    structural: list[dict] = []
    semantic: list[dict] = []
    sources = {"C1": "1" * 64, "C2": "3" * 64}
    keys = [
        ("C1", None, "deterministic_baseline", "VALID", "FAITHFUL"),
        ("C2", None, "deterministic_baseline", "VALID", "FAITHFUL"),
        ("C1", "M1", "direct_structured_llm", "VALID", "UNFAITHFUL"),
        ("C1", "M1", "mapping_aware_llm", "VALID", "FAITHFUL"),
        (
            "C1",
            "M1",
            "mapping_aware_plus_syntax_repair",
            "POLICY_UNRESOLVED",
            "INDETERMINATE",
        ),
        ("C2", "M1", "direct_structured_llm", "INVALID", "INDETERMINATE"),
        (
            "C2",
            "M1",
            "mapping_aware_llm",
            "MEASUREMENT_FAILURE",
            "INDETERMINATE",
        ),
        (
            "C2",
            "M1",
            "mapping_aware_plus_syntax_repair",
            "VALID",
            "INDETERMINATE",
        ),
    ]
    hex_chars = "123456789abcdef"
    for index, (case_id, model_key, arm_id, outcome, verdict) in enumerate(
        keys,
        start=1,
    ):
        structural.append(
            {
                "case_id": case_id,
                "model_key": model_key,
                "arm_id": arm_id,
                "source_input_sha256": sources[case_id],
                "structural_outcome": outcome,
                "validator_evidence_sha256": hex_chars[index - 1] * 64,
            }
        )
        if outcome != "VALID":
            reason = "STRUCTURAL_NOT_VALID"
        elif verdict == "INDETERMINATE":
            reason = "VERIFIER_RUNTIME_INDETERMINATE"
        else:
            reason = "PRIMARY_SEMANTIC_EVALUATION"
        semantic.append(
            {
                "case_id": case_id,
                "model_key": model_key,
                "arm_id": arm_id,
                "source_input_sha256": sources[case_id],
                "semantic_verdict": verdict,
                "verifier_evidence_sha256": hex_chars[index + 6] * 64,
                "evaluation_reason": reason,
            }
        )
    return structural, semantic


def test_analysis_rows_preserve_all_structural_and_semantic_states() -> None:
    structural, semantic = _key_records()

    rows = build_analysis_rows(
        sealed_case_manifest=_sealed(),
        model_keys=["M1"],
        structural_records=structural,
        semantic_records=semantic,
    )

    assert len(rows) == 2
    first = rows[0]
    assert first["case_id"] == "C1"
    assert first["arms"]["deterministic_baseline"]["vfy_success"] is True
    assert first["arms"]["direct_structured_llm"]["vur_eligible"] is True
    assert first["arms"]["direct_structured_llm"]["vfy_success"] is False
    repair = first["arms"]["mapping_aware_plus_syntax_repair"]
    assert repair["structural_outcome"] == "POLICY_UNRESOLVED"
    assert repair["semantic_verdict"] == "INDETERMINATE"
    assert repair["vur_eligible"] is False
    assert repair["vfy_success"] is False

    second = rows[1]
    direct = second["arms"]["direct_structured_llm"]
    assert direct["structural_outcome"] == "INVALID"
    assert direct["semantic_verdict"] == "INDETERMINATE"
    assert direct["semantic_evaluation_reason"] == "STRUCTURAL_NOT_VALID"
    mapping = second["arms"]["mapping_aware_llm"]
    assert mapping["structural_outcome"] == "MEASUREMENT_FAILURE"
    repair = second["arms"]["mapping_aware_plus_syntax_repair"]
    assert repair["structural_outcome"] == "VALID"
    assert repair["semantic_verdict"] == "INDETERMINATE"
    assert repair["semantic_evaluation_reason"] == (
        "VERIFIER_RUNTIME_INDETERMINATE"
    )


def test_analysis_rows_require_exact_planned_arm_coverage() -> None:
    structural, semantic = _key_records()
    semantic.pop()

    with pytest.raises(ValueError, match="does not match planned arm set"):
        build_analysis_rows(
            sealed_case_manifest=_sealed(),
            model_keys=["M1"],
            structural_records=structural,
            semantic_records=semantic,
        )


def test_analysis_rows_reject_source_hash_not_in_sealed_manifest() -> None:
    structural, semantic = _key_records()
    structural[2]["source_input_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="does not match sealed case"):
        build_analysis_rows(
            sealed_case_manifest=_sealed(),
            model_keys=["M1"],
            structural_records=structural,
            semantic_records=semantic,
        )


def test_nonvalid_structural_output_cannot_receive_determinate_semantics() -> None:
    structural, semantic = _key_records()
    semantic[5]["semantic_verdict"] = "FAITHFUL"
    semantic[5]["evaluation_reason"] = "PRIMARY_SEMANTIC_EVALUATION"

    with pytest.raises(ValueError, match="non-VALID structural output"):
        build_analysis_rows(
            sealed_case_manifest=_sealed(),
            model_keys=["M1"],
            structural_records=structural,
            semantic_records=semantic,
        )


def test_valid_runtime_indeterminate_requires_explicit_reason() -> None:
    structural, semantic = _key_records()
    semantic[7]["evaluation_reason"] = "PRIMARY_SEMANTIC_EVALUATION"

    with pytest.raises(ValueError, match="runtime-indeterminate"):
        build_analysis_rows(
            sealed_case_manifest=_sealed(),
            model_keys=["M1"],
            structural_records=structural,
            semantic_records=semantic,
        )


def test_duplicate_evidence_identity_is_rejected() -> None:
    structural, semantic = _key_records()
    structural.append(deepcopy(structural[0]))

    with pytest.raises(ValueError, match="duplicate structural evidence"):
        build_analysis_rows(
            sealed_case_manifest=_sealed(),
            model_keys=["M1"],
            structural_records=structural,
            semantic_records=semantic,
        )
