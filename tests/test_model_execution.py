import json
from pathlib import Path

import jsonschema

from fhirbridge.model_execution import (
    build_failure_record,
    build_success_record,
    execution_record_to_dict,
)
from fhirbridge.model_strategies import (
    DIRECT_STRATEGY,
    REPAIR_STRATEGY,
    process_strategy_output,
)

_SCHEMA = Path("models/schema/model_execution_record.schema.json")


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def test_success_record_hashes_actual_direct_output_without_repair() -> None:
    output = process_strategy_output(DIRECT_STRATEGY, "MSH|^~\\&|APP\r")
    record = build_success_record(
        execution_id="EXEC-001",
        case_id="CASE-001",
        model_key="M1",
        strategy_output=output,
        request_started_at="2026-10-10T10:00:00Z",
        request_finished_at="2026-10-10T10:00:01Z",
        provider_request_id="REQ-001",
    )
    document = execution_record_to_dict(record)

    jsonschema.Draft202012Validator(_schema()).validate(document)
    assert document["raw_response_sha256"] == document["final_response_sha256"]
    assert document["syntax_repair_applied"] is False
    assert document["syntax_repair_operations"] == []


def test_repair_record_hashes_raw_and_repaired_outputs_separately() -> None:
    fence = chr(96) * 3
    raw = fence + "hl7\nMSH|^~\\&|APP\n" + fence
    output = process_strategy_output(REPAIR_STRATEGY, raw)
    record = build_success_record(
        execution_id="EXEC-002",
        case_id="CASE-001",
        model_key="M1",
        strategy_output=output,
        request_started_at="2026-10-10T10:00:00Z",
        request_finished_at="2026-10-10T10:00:01Z",
    )
    document = execution_record_to_dict(record)

    jsonschema.Draft202012Validator(_schema()).validate(document)
    assert document["raw_response_sha256"] != document["final_response_sha256"]
    assert document["syntax_repair_applied"] is True
    assert "remove_single_outer_markdown_fence" in (
        document["syntax_repair_operations"]
    )


def test_failure_record_has_no_response_hashes_or_repair() -> None:
    record = build_failure_record(
        execution_id="EXEC-003",
        case_id="CASE-002",
        model_key="M1",
        strategy_id=DIRECT_STRATEGY,
        outcome_class="MEASUREMENT_FAILURE_TIMEOUT",
        request_started_at="2026-10-10T10:00:00Z",
        request_finished_at="2026-10-10T10:02:00Z",
        error_summary="Provider call exceeded frozen 120 second timeout.",
    )
    document = execution_record_to_dict(record)

    jsonschema.Draft202012Validator(_schema()).validate(document)
    assert document["raw_response_sha256"] is None
    assert document["final_response_sha256"] is None
    assert document["syntax_repair_applied"] is False
    assert document["syntax_repair_operations"] == []


def test_schema_forbids_attempt_number_greater_than_one() -> None:
    record = build_failure_record(
        execution_id="EXEC-004",
        case_id="CASE-003",
        model_key="M1",
        strategy_id=DIRECT_STRATEGY,
        outcome_class="MEASUREMENT_FAILURE_TRANSPORT",
        request_started_at="2026-10-10T10:00:00Z",
        request_finished_at="2026-10-10T10:00:01Z",
        error_summary="Transport error.",
    )
    document = execution_record_to_dict(record)
    document["attempt_number"] = 2

    errors = list(
        jsonschema.Draft202012Validator(_schema()).iter_errors(document)
    )
    assert errors


def test_schema_forbids_hashes_on_measurement_failure() -> None:
    record = build_failure_record(
        execution_id="EXEC-005",
        case_id="CASE-004",
        model_key="M1",
        strategy_id=DIRECT_STRATEGY,
        outcome_class="MEASUREMENT_FAILURE_PROVIDER_5XX",
        request_started_at="2026-10-10T10:00:00Z",
        request_finished_at="2026-10-10T10:00:01Z",
        error_summary="Provider returned 503.",
    )
    document = execution_record_to_dict(record)
    document["raw_response_sha256"] = "a" * 64

    errors = list(
        jsonschema.Draft202012Validator(_schema()).iter_errors(document)
    )
    assert errors
