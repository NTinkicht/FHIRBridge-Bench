import importlib.util
import json
from pathlib import Path

import pytest
import yaml

_MODULE_PATH = Path("runs/build_confirmatory_result_manifest.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_confirmatory_result_manifest",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _write_jsonl(path: Path, count: int, prefix: str) -> None:
    path.write_text(
        "".join(
            json.dumps({"record_id": f"{prefix}-{index}"}) + "\n"
            for index in range(count)
        ),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}

    bundle = tmp_path / "sealed.bin"
    bundle.write_bytes(b"sealed-confirmatory-bundle")
    paths["bundle"] = bundle

    raw = tmp_path / "execution-records.jsonl"
    _write_jsonl(raw, 6, "EXEC")
    paths["raw"] = raw

    baseline = tmp_path / "baseline.jsonl"
    _write_jsonl(baseline, 2, "BASE")
    paths["baseline"] = baseline

    structural = tmp_path / "structural.jsonl"
    _write_jsonl(structural, 8, "STRUCT")
    paths["structural"] = structural

    semantic = tmp_path / "semantic.jsonl"
    _write_jsonl(semantic, 8, "SEM")
    paths["semantic"] = semantic

    analysis = tmp_path / "analysis.jsonl"
    _write_jsonl(analysis, 2, "ANALYSIS")
    paths["analysis"] = analysis

    run_plan = tmp_path / "run-plan.yaml"
    run_plan.write_text(
        yaml.safe_dump(
            {
                "repository_commit": "abcdef1",
                "sealed_set": {
                    "bundle_id": "SEALED-001",
                    "bundle_sha256": _MODULE._sha256(bundle),
                    "case_manifest_sha256": "c" * 64,
                    "case_count": 2,
                },
                "frozen_artifacts": {
                    "execution_record_schema_sha256": "e" * 64,
                },
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
    paths["run_plan"] = run_plan

    schema_report = tmp_path / "schema-validation.json"
    schema_report.write_text(
        json.dumps(
            {
                "passed": True,
                "record_count": 6,
                "valid_record_count": 6,
                "invalid_record_count": 0,
                "batch_errors": [],
                "input_sha256": _MODULE._sha256(raw),
                "execution_record_schema_sha256": "e" * 64,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["schema_report"] = schema_report

    audit = tmp_path / "execution-audit.json"
    audit.write_text(
        json.dumps(
            {
                "complete": True,
                "blockers": [],
                "source_hash_binding_verified": True,
                "inputs": {
                    "run_plan_sha256": _MODULE._sha256(run_plan),
                    "sealed_case_manifest_sha256": "c" * 64,
                    "execution_records_sha256": _MODULE._sha256(raw),
                    "deterministic_baseline_sha256": _MODULE._sha256(baseline),
                },
                "counts": {
                    "provider_call_count": 4,
                    "derived_repair_count": 2,
                    "deterministic_baseline_count": 2,
                    "total_arm_output_count": 8,
                    "outcome_counts": {"RESPONSE_RECEIVED": 6},
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["audit"] = audit

    analysis_build = tmp_path / "analysis-dataset-build.json"
    analysis_build.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "run_plan_sha256": _MODULE._sha256(run_plan),
                "structural_evidence_sha256": _MODULE._sha256(structural),
                "semantic_evidence_sha256": _MODULE._sha256(semantic),
                "analysis_dataset_sha256": _MODULE._sha256(analysis),
                "analysis_row_count": 2,
                "no_silent_exclusion_verified": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["analysis_build"] = analysis_build
    return paths


def _build(paths: dict[str, Path]) -> dict:
    return _MODULE.build_result_manifest(
        run_plan_path=paths["run_plan"],
        sealed_bundle_path=paths["bundle"],
        raw_execution_records_path=paths["raw"],
        deterministic_baseline_path=paths["baseline"],
        execution_schema_validation_path=paths["schema_report"],
        execution_audit_path=paths["audit"],
        structural_validation_path=paths["structural"],
        semantic_verification_path=paths["semantic"],
        analysis_dataset_build_path=paths["analysis_build"],
        analysis_ready_dataset_path=paths["analysis"],
        result_manifest_id="RESULTS-001",
        created_at="2026-10-21T10:00:00Z",
        repository_commit="abcdef1",
    )


def test_result_manifest_builder_hashes_and_counts_all_artifacts(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)

    result = _build(paths)

    assert result["status"] == "execution_complete_audited"
    assert result["run_plan_sha256"] == _MODULE._sha256(paths["run_plan"])
    assert result["sealed_bundle_sha256"] == _MODULE._sha256(paths["bundle"])
    assert result["raw_execution_records"]["record_count"] == 6
    assert result["deterministic_baseline_outputs"]["record_count"] == 2
    assert result["structural_validation_evidence"]["record_count"] == 8
    assert result["semantic_verification_evidence"]["record_count"] == 8
    assert result["analysis_ready_dataset"]["record_count"] == 2


def test_result_manifest_builder_rejects_tampered_execution_audit_input_hash(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    audit["inputs"]["execution_records_sha256"] = "f" * 64
    paths["audit"].write_text(
        json.dumps(audit, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="execution_records_sha256"):
        _build(paths)


def test_result_manifest_builder_rejects_schema_count_inconsistency(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    report = json.loads(paths["schema_report"].read_text(encoding="utf-8"))
    report["valid_record_count"] = 5
    paths["schema_report"].write_text(
        json.dumps(report, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="valid count"):
        _build(paths)


def test_result_manifest_builder_rejects_audit_count_inconsistency(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    audit["counts"]["provider_call_count"] = 3
    paths["audit"].write_text(
        json.dumps(audit, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="provider_call_count"):
        _build(paths)


def test_result_manifest_builder_rejects_repository_commit_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)

    with pytest.raises(ValueError, match="repository_commit"):
        _MODULE.build_result_manifest(
            run_plan_path=paths["run_plan"],
            sealed_bundle_path=paths["bundle"],
            raw_execution_records_path=paths["raw"],
            deterministic_baseline_path=paths["baseline"],
            execution_schema_validation_path=paths["schema_report"],
            execution_audit_path=paths["audit"],
            structural_validation_path=paths["structural"],
            semantic_verification_path=paths["semantic"],
            analysis_ready_dataset_path=paths["analysis"],
            result_manifest_id="RESULTS-001",
            created_at="2026-10-21T10:00:00Z",
            repository_commit="deadbee",
        )


def test_result_manifest_builder_rejects_analysis_build_output_hash_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    report = json.loads(
        paths["analysis_build"].read_text(encoding="utf-8")
    )
    report["analysis_dataset_sha256"] = "f" * 64
    paths["analysis_build"].write_text(
        json.dumps(report, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="analysis dataset build output hash"):
        _build(paths)
