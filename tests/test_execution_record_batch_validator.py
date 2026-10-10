import importlib.util
import json
from pathlib import Path

from fhirbridge.model_execution import (
    build_success_record,
    execution_record_to_dict,
)
from fhirbridge.model_strategies import (
    DIRECT_STRATEGY,
    MAPPING_STRATEGY,
    process_strategy_output,
)

_MODULE_PATH = Path("runs/validate_execution_records.py")
_SPEC = importlib.util.spec_from_file_location(
    "validate_execution_records",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_FREEZE_HASH = "a" * 64
_SOURCE_HASH = "b" * 64
_PROMPT_HASH = "c" * 64
_MAPPING_HASH = "d" * 64


def _record(strategy_id: str, execution_id: str) -> dict:
    output = process_strategy_output(
        strategy_id,
        "MSH|^~\\&|APP\r",
    )
    return execution_record_to_dict(
        build_success_record(
            execution_id=execution_id,
            case_id="CASE-001",
            model_key="M1",
            model_prompt_freeze_sha256=_FREEZE_HASH,
            source_input_sha256=_SOURCE_HASH,
            rendered_prompt_sha256=_PROMPT_HASH,
            mapping_context_sha256=(
                _MAPPING_HASH
                if strategy_id == MAPPING_STRATEGY
                else None
            ),
            strategy_output=output,
            request_started_at="2026-10-10T10:00:00Z",
            request_finished_at="2026-10-10T10:00:01Z",
        )
    )


def test_execution_jsonl_validator_accepts_schema_valid_records(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "records.jsonl"
    rows = [
        _record(DIRECT_STRATEGY, "EXEC-1"),
        _record(MAPPING_STRATEGY, "EXEC-2"),
    ]
    input_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = _MODULE.validate_jsonl(input_path)

    assert report["passed"] is True
    assert report["execution_record_schema_version"] == "0.3.0"
    assert report["record_count"] == 2
    assert report["valid_record_count"] == 2
    assert report["invalid_record_count"] == 0
    assert report["duplicate_execution_ids_checked"] is True


def test_execution_jsonl_validator_rejects_duplicate_execution_id(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "records.jsonl"
    row = _record(DIRECT_STRATEGY, "EXEC-DUP")
    input_path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )

    report = _MODULE.validate_jsonl(input_path)

    assert report["passed"] is False
    assert report["invalid_record_count"] == 1
    assert "duplicated" in report["invalid_records"][0]["errors"][-1]


def test_execution_jsonl_validator_rejects_schema_invalid_record(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "records.jsonl"
    row = _record(DIRECT_STRATEGY, "EXEC-BAD")
    row["model_prompt_freeze_sha256"] = "bad"
    input_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    report = _MODULE.validate_jsonl(input_path)

    assert report["passed"] is False
    assert report["invalid_record_count"] == 1
    assert any(
        "model_prompt_freeze_sha256" in error
        for error in report["invalid_records"][0]["errors"]
    )


def test_execution_jsonl_validator_rejects_empty_or_malformed_batch(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    empty_report = _MODULE.validate_jsonl(empty)

    assert empty_report["passed"] is False
    assert empty_report["record_count"] == 0

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("{not-json}\n", encoding="utf-8")
    malformed_report = _MODULE.validate_jsonl(malformed)

    assert malformed_report["passed"] is False
    assert malformed_report["invalid_record_count"] == 1
    assert "invalid JSON" in malformed_report["invalid_records"][0]["errors"][0]
