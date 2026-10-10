import importlib.util
import json
from pathlib import Path

import pytest
import yaml

_MODULE_PATH = Path("runs/audit_confirmatory_execution.py")
_SPEC = importlib.util.spec_from_file_location(
    "audit_confirmatory_execution_cli",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_MODEL_FREEZE_HASH = "1" * 64
_SOURCE_HASHES = {"C1": "2" * 64, "C2": "3" * 64}
_PROMPT_HASH = "4" * 64
_MAPPING_HASH = "5" * 64


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _provider(
    execution_id: str,
    case_id: str,
    strategy_id: str,
    *,
    success: bool = True,
) -> dict:
    digest = ("a" if case_id == "C1" else "b") * 64
    return {
        "schema_version": "0.3.0",
        "execution_id": execution_id,
        "case_id": case_id,
        "model_key": "M1",
        "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
        "source_input_sha256": _SOURCE_HASHES[case_id],
        "rendered_prompt_sha256": _PROMPT_HASH,
        "mapping_context_sha256": (
            _MAPPING_HASH if strategy_id == "mapping_aware_llm" else None
        ),
        "strategy_id": strategy_id,
        "generation_source": "provider_call",
        "attempt_number": 1,
        "source_execution_id": None,
        "request_started_at": "2026-10-20T10:00:00Z",
        "request_finished_at": "2026-10-20T10:00:01Z",
        "outcome_class": (
            "RESPONSE_RECEIVED"
            if success
            else "MEASUREMENT_FAILURE_TIMEOUT"
        ),
        "raw_response_sha256": digest if success else None,
        "final_response_sha256": digest if success else None,
        "syntax_repair_applied": False,
        "syntax_repair_operations": [],
        "provider_request_id": f"REQ-{execution_id}",
        "error_summary": None if success else "Timeout.",
    }


def _repair(
    execution_id: str,
    case_id: str,
    source_execution_id: str,
    *,
    mapping_success: bool,
) -> dict:
    raw_digest = ("a" if case_id == "C1" else "b") * 64
    return {
        "schema_version": "0.3.0",
        "execution_id": execution_id,
        "case_id": case_id,
        "model_key": "M1",
        "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
        "source_input_sha256": _SOURCE_HASHES[case_id],
        "rendered_prompt_sha256": None,
        "mapping_context_sha256": _MAPPING_HASH,
        "strategy_id": "mapping_aware_plus_syntax_repair",
        "generation_source": "reuse_mapping_aware_raw_output",
        "attempt_number": None,
        "source_execution_id": source_execution_id,
        "request_started_at": "2026-10-20T10:00:01Z",
        "request_finished_at": "2026-10-20T10:00:01Z",
        "outcome_class": (
            "RESPONSE_RECEIVED"
            if mapping_success
            else "MEASUREMENT_FAILURE_UPSTREAM"
        ),
        "raw_response_sha256": raw_digest if mapping_success else None,
        "final_response_sha256": ("c" * 64) if mapping_success else None,
        "syntax_repair_applied": mapping_success,
        "syntax_repair_operations": (
            ["normalize_segment_terminators"] if mapping_success else []
        ),
        "provider_request_id": None,
        "error_summary": None if mapping_success else "Upstream mapping failed.",
    }


def _records() -> list[dict]:
    return [
        _provider("C1-D", "C1", "direct_structured_llm"),
        _provider("C1-M", "C1", "mapping_aware_llm"),
        _repair("C1-R", "C1", "C1-M", mapping_success=True),
        _provider("C2-D", "C2", "direct_structured_llm", success=False),
        _provider("C2-M", "C2", "mapping_aware_llm", success=False),
        _repair("C2-R", "C2", "C2-M", mapping_success=False),
    ]


def _fixture(tmp_path: Path) -> dict[str, Path]:
    run_plan = tmp_path / "run-plan.yaml"
    run_plan.write_text(
        yaml.safe_dump(
            {
                "frozen_artifacts": {
                    "model_prompt_configuration_sha256": _MODEL_FREEZE_HASH,
                    "deterministic_baseline_renderer_sha256": "d" * 64,
                },
                "sealed_set": {"case_count": 2},
                "model_keys": ["M1"],
                "expected_execution_counts": {
                    "provider_generation_calls": 4,
                    "derived_repair_outputs": 2,
                    "deterministic_baseline_outputs": 2,
                    "total_arm_outputs": 8,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest = tmp_path / "sealed-cases.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
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
                        "source_input_sha256": _SOURCE_HASHES["C1"],
                        "canonical_graph_sha256": "6" * 64,
                    },
                    {
                        "case_id": "C2",
                        "scenario_family": "LAB-006",
                        "source_input_sha256": _SOURCE_HASHES["C2"],
                        "canonical_graph_sha256": "7" * 64,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    executions = tmp_path / "execution-records.jsonl"
    _write_jsonl(executions, _records())

    baseline = tmp_path / "baseline.jsonl"
    _write_jsonl(
        baseline,
        [
            {
                "schema_version": "0.1.0",
                "execution_id": "BASE-C1",
                "case_id": "C1",
                "source_input_sha256": _SOURCE_HASHES["C1"],
                "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
                "renderer_component_sha256": "d" * 64,
                "outcome_class": "RESPONSE_RECEIVED",
                "output_sha256": "8" * 64,
                "error_summary": None,
            },
            {
                "schema_version": "0.1.0",
                "execution_id": "BASE-C2",
                "case_id": "C2",
                "source_input_sha256": _SOURCE_HASHES["C2"],
                "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
                "renderer_component_sha256": "d" * 64,
                "outcome_class": "RESPONSE_RECEIVED",
                "output_sha256": "9" * 64,
                "error_summary": None,
            },
        ],
    )
    return {
        "run_plan": run_plan,
        "manifest": manifest,
        "executions": executions,
        "baseline": baseline,
    }


def test_execution_audit_cli_binds_records_to_sealed_sources(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)

    report = _MODULE.build_execution_audit(
        run_plan_path=paths["run_plan"],
        sealed_case_manifest_path=paths["manifest"],
        execution_records_path=paths["executions"],
        deterministic_baseline_path=paths["baseline"],
    )

    assert report["complete"] is True
    assert report["blockers"] == []
    assert report["source_hash_binding_verified"] is True
    assert report["counts"]["provider_call_count"] == 4
    assert report["counts"]["derived_repair_count"] == 2


def test_execution_audit_cli_rejects_source_hash_not_in_sealed_manifest(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    records = _records()
    for record in records:
        if record["case_id"] == "C1":
            record["source_input_sha256"] = "f" * 64
    _write_jsonl(paths["executions"], records)

    report = _MODULE.build_execution_audit(
        run_plan_path=paths["run_plan"],
        sealed_case_manifest_path=paths["manifest"],
        execution_records_path=paths["executions"],
        deterministic_baseline_path=paths["baseline"],
    )

    assert report["complete"] is False
    assert report["source_hash_binding_verified"] is False
    assert any(
        "C1: source_input_sha256 does not match sealed manifest" in blocker
        for blocker in report["blockers"]
    )


def test_execution_audit_cli_requires_baseline_exact_case_coverage(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    _write_jsonl(
        paths["baseline"],
        [
            {
                "schema_version": "0.1.0",
                "execution_id": "BASE-C1",
                "case_id": "C1",
                "source_input_sha256": _SOURCE_HASHES["C1"],
                "model_prompt_freeze_sha256": _MODEL_FREEZE_HASH,
                "renderer_component_sha256": "d" * 64,
                "outcome_class": "RESPONSE_RECEIVED",
                "output_sha256": "8" * 64,
                "error_summary": None,
            }
        ],
    )

    report = _MODULE.build_execution_audit(
        run_plan_path=paths["run_plan"],
        sealed_case_manifest_path=paths["manifest"],
        execution_records_path=paths["executions"],
        deterministic_baseline_path=paths["baseline"],
    )

    assert report["complete"] is False
    assert any(
        "deterministic baseline missing cases: C2" in blocker
        for blocker in report["blockers"]
    )


def test_execution_audit_cli_rejects_wrong_baseline_source_hash(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    records = [
        json.loads(line)
        for line in paths["baseline"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records[0]["source_input_sha256"] = "f" * 64
    _write_jsonl(paths["baseline"], records)

    with pytest.raises(ValueError, match="baseline source hash"):
        _MODULE.build_execution_audit(
            run_plan_path=paths["run_plan"],
            sealed_case_manifest_path=paths["manifest"],
            execution_records_path=paths["executions"],
            deterministic_baseline_path=paths["baseline"],
        )


def test_execution_audit_cli_rejects_wrong_baseline_renderer_hash(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    records = [
        json.loads(line)
        for line in paths["baseline"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records[0]["renderer_component_sha256"] = "f" * 64
    _write_jsonl(paths["baseline"], records)

    with pytest.raises(ValueError, match="baseline renderer hash"):
        _MODULE.build_execution_audit(
            run_plan_path=paths["run_plan"],
            sealed_case_manifest_path=paths["manifest"],
            execution_records_path=paths["executions"],
            deterministic_baseline_path=paths["baseline"],
        )
