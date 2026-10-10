from copy import deepcopy

from fhirbridge.confirmatory_execution_audit import (
    audit_confirmatory_execution,
)


_MODEL_FREEZE_HASH = "1" * 64
_SOURCE_HASHES = {"C1": "2" * 64, "C2": "3" * 64}
_PROMPT_HASH = "4" * 64
_MAPPING_CONTEXT_HASH = "5" * 64


def _plan() -> dict:
    return {
        "frozen_artifacts": {
            "model_prompt_configuration_sha256": _MODEL_FREEZE_HASH,
        },
        "sealed_set": {"case_count": 2},
        "model_keys": ["M1"],
        "expected_execution_counts": {
            "provider_generation_calls": 4,
            "derived_repair_outputs": 2,
            "deterministic_baseline_outputs": 2,
            "total_arm_outputs": 8,
        },
    }


def _provider(
    execution_id: str,
    case_id: str,
    strategy_id: str,
    *,
    success: bool = True,
    digest: str = "a" * 64,
) -> dict:
    return {
        "execution_id": execution_id,
        "case_id": case_id,
        "model_key": "M1",
        "schema_version": "0.3.0",
        "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
        "source_input_sha256": _SOURCE_HASHES[case_id],
        "rendered_prompt_sha256": _PROMPT_HASH,
        "mapping_context_sha256": (
            _MAPPING_CONTEXT_HASH
            if strategy_id == "mapping_aware_llm"
            else None
        ),
        "strategy_id": strategy_id,
        "generation_source": "provider_call",
        "attempt_number": 1,
        "source_execution_id": None,
        "provider_request_id": f"REQ-{execution_id}",
        "outcome_class": (
            "RESPONSE_RECEIVED"
            if success
            else "MEASUREMENT_FAILURE_TIMEOUT"
        ),
        "raw_response_sha256": digest if success else None,
        "final_response_sha256": digest if success else None,
        "error_summary": None if success else "Provider timeout.",
    }


def _repair_success(
    execution_id: str,
    case_id: str,
    *,
    source_execution_id: str,
    raw_digest: str,
    final_digest: str = "b" * 64,
) -> dict:
    return {
        "execution_id": execution_id,
        "case_id": case_id,
        "model_key": "M1",
        "schema_version": "0.3.0",
        "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
        "source_input_sha256": _SOURCE_HASHES[case_id],
        "rendered_prompt_sha256": None,
        "mapping_context_sha256": _MAPPING_CONTEXT_HASH,
        "strategy_id": "mapping_aware_plus_syntax_repair",
        "generation_source": "reuse_mapping_aware_raw_output",
        "attempt_number": None,
        "source_execution_id": source_execution_id,
        "provider_request_id": None,
        "outcome_class": "RESPONSE_RECEIVED",
        "raw_response_sha256": raw_digest,
        "final_response_sha256": final_digest,
        "error_summary": None,
    }


def _repair_upstream_failure(
    execution_id: str,
    case_id: str,
    *,
    source_execution_id: str,
) -> dict:
    return {
        "execution_id": execution_id,
        "case_id": case_id,
        "model_key": "M1",
        "schema_version": "0.3.0",
        "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
        "source_input_sha256": _SOURCE_HASHES[case_id],
        "rendered_prompt_sha256": None,
        "mapping_context_sha256": _MAPPING_CONTEXT_HASH,
        "strategy_id": "mapping_aware_plus_syntax_repair",
        "generation_source": "reuse_mapping_aware_raw_output",
        "attempt_number": None,
        "source_execution_id": source_execution_id,
        "provider_request_id": None,
        "outcome_class": "MEASUREMENT_FAILURE_UPSTREAM",
        "raw_response_sha256": None,
        "final_response_sha256": None,
        "error_summary": "Mapping-aware provider call failed upstream.",
    }


def _records() -> list[dict]:
    mapping_hash = "c" * 64
    return [
        _provider(
            "C1-D",
            "C1",
            "direct_structured_llm",
            digest="d" * 64,
        ),
        _provider(
            "C1-M",
            "C1",
            "mapping_aware_llm",
            digest=mapping_hash,
        ),
        _repair_success(
            "C1-R",
            "C1",
            source_execution_id="C1-M",
            raw_digest=mapping_hash,
        ),
        _provider(
            "C2-D",
            "C2",
            "direct_structured_llm",
            success=False,
        ),
        _provider(
            "C2-M",
            "C2",
            "mapping_aware_llm",
            success=False,
        ),
        _repair_upstream_failure(
            "C2-R",
            "C2",
            source_execution_id="C2-M",
        ),
    ]


def test_complete_execution_cross_product_passes() -> None:
    result = audit_confirmatory_execution(
        _plan(),
        _records(),
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert result.complete
    assert result.blockers == ()
    assert result.provider_call_count == 4
    assert result.derived_repair_count == 2
    assert result.deterministic_baseline_count == 2
    assert result.total_arm_output_count == 8
    assert result.outcome_counts["RESPONSE_RECEIVED"] == 3
    assert result.outcome_counts["MEASUREMENT_FAILURE_TIMEOUT"] == 2
    assert result.outcome_counts["MEASUREMENT_FAILURE_UPSTREAM"] == 1


def test_repair_must_reference_same_case_model_mapping_execution() -> None:
    records = _records()
    repair = next(item for item in records if item["execution_id"] == "C1-R")
    repair["source_execution_id"] = "C2-M"

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any("source_execution_id" in item for item in result.blockers)


def test_repair_raw_hash_must_equal_mapping_raw_hash() -> None:
    records = _records()
    repair = next(item for item in records if item["execution_id"] == "C1-R")
    repair["raw_response_sha256"] = "f" * 64

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any("raw hash does not match" in item for item in result.blockers)


def test_failed_mapping_requires_explicit_upstream_repair_failure() -> None:
    records = _records()
    repair_index = next(
        index
        for index, item in enumerate(records)
        if item["execution_id"] == "C2-R"
    )
    records[repair_index] = _repair_success(
        "C2-R",
        "C2",
        source_execution_id="C2-M",
        raw_digest="a" * 64,
    )

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any(
        "failed mapping must propagate" in item for item in result.blockers
    )


def test_successful_mapping_cannot_be_labeled_upstream_failure() -> None:
    records = _records()
    repair_index = next(
        index
        for index, item in enumerate(records)
        if item["execution_id"] == "C1-R"
    )
    records[repair_index] = _repair_upstream_failure(
        "C1-R",
        "C1",
        source_execution_id="C1-M",
    )

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any(
        "upstream repair failure is invalid" in item
        for item in result.blockers
    )


def test_missing_arm_record_fails_completeness() -> None:
    records = [
        item for item in _records()
        if item["execution_id"] != "C1-D"
    ]

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any("missing planned LLM arm records" in item for item in result.blockers)
    assert any("provider_generation_calls" in item for item in result.blockers)
    assert any("total_arm_outputs" in item for item in result.blockers)


def test_duplicate_case_model_strategy_record_is_rejected() -> None:
    records = _records()
    duplicate = deepcopy(records[0])
    duplicate["execution_id"] = "C1-D-DUP"
    records.append(duplicate)

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any("duplicate execution record" in item for item in result.blockers)


def test_baseline_must_cover_exact_sealed_case_set() -> None:
    result = audit_confirmatory_execution(
        _plan(),
        _records(),
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert not result.complete
    assert any("deterministic baseline missing cases" in item for item in result.blockers)
    assert any("deterministic_baseline_outputs" in item for item in result.blockers)


def test_execution_records_must_match_run_plan_model_freeze_hash() -> None:
    records = _records()
    records[0]["model_prompt_freeze_sha256"] = "f" * 64

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any(
        "model_prompt_freeze_sha256 does not match run plan" in item
        for item in result.blockers
    )


def test_source_input_hash_must_match_across_all_arms_for_case() -> None:
    records = _records()
    mapping = next(item for item in records if item["execution_id"] == "C1-M")
    mapping["source_input_sha256"] = "e" * 64

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any(
        "source_input_sha256 differs across planned arms" in item
        for item in result.blockers
    )


def test_repair_mapping_context_must_match_mapping_arm() -> None:
    records = _records()
    repair = next(item for item in records if item["execution_id"] == "C1-R")
    repair["mapping_context_sha256"] = "e" * 64

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any(
        "repair mapping-context hash does not match mapping arm" in item
        for item in result.blockers
    )


def test_execution_schema_version_must_match_frozen_record_version() -> None:
    records = _records()
    records[0]["schema_version"] = "0.2.0"

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
    )

    assert not result.complete
    assert any("schema_version must be 0.3.0" in item for item in result.blockers)


def test_execution_source_hash_must_match_frozen_sealed_manifest() -> None:
    records = _records()
    for record in records:
        if record["case_id"] == "C1":
            record["source_input_sha256"] = "e" * 64

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert not result.complete
    assert any(
        "C1: source_input_sha256 does not match sealed manifest" in item
        for item in result.blockers
    )


def test_frozen_source_hash_map_must_cover_exact_sealed_case_set() -> None:
    result = audit_confirmatory_execution(
        _plan(),
        _records(),
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256={"C1": _SOURCE_HASHES["C1"]},
    )

    assert not result.complete
    assert any(
        "sealed source-hash map missing cases: C2" in item
        for item in result.blockers
    )


def test_zero_frozen_source_hash_is_rejected() -> None:
    result = audit_confirmatory_execution(
        _plan(),
        _records(),
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256={
            "C1": "0" * 64,
            "C2": _SOURCE_HASHES["C2"],
        },
    )

    assert not result.complete
    assert any(
        "C1: frozen source_input_sha256 is missing or invalid" in item
        for item in result.blockers
    )


def test_unknown_outcome_class_blocks_execution_audit() -> None:
    records = _records()
    records[0]["outcome_class"] = "UNKNOWN_PROVIDER_STATE"

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert not result.complete
    assert any(
        "unsupported outcome_class: UNKNOWN_PROVIDER_STATE" in item
        for item in result.blockers
    )


def test_measurement_failure_cannot_carry_response_hashes() -> None:
    records = _records()
    failed = next(item for item in records if item["execution_id"] == "C2-D")
    failed["raw_response_sha256"] = "f" * 64

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert not result.complete
    assert any(
        "measurement failure must not carry response hashes" in item
        for item in result.blockers
    )


def test_provider_strategy_cannot_use_repair_failure_class() -> None:
    records = _records()
    failed = next(item for item in records if item["execution_id"] == "C2-D")
    failed["outcome_class"] = "MEASUREMENT_FAILURE_UPSTREAM"

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert not result.complete
    assert any(
        "provider strategy cannot use repair failure class" in item
        for item in result.blockers
    )


def test_repair_strategy_cannot_use_provider_failure_class() -> None:
    records = _records()
    failed = next(item for item in records if item["execution_id"] == "C2-R")
    failed["outcome_class"] = "MEASUREMENT_FAILURE_TIMEOUT"

    result = audit_confirmatory_execution(
        _plan(),
        records,
        sealed_case_ids={"C1", "C2"},
        deterministic_baseline_case_ids={"C1", "C2"},
        expected_source_input_sha256=_SOURCE_HASHES,
    )

    assert not result.complete
    assert any(
        "repair strategy cannot use provider failure class" in item
        for item in result.blockers
    )
