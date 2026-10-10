"""Deterministically assemble the audited confirmatory result manifest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.confirmatory_result_manifest import (
    assess_confirmatory_result_manifest,
)

_SCHEMA = Path("runs/schema/confirmatory_result_manifest.schema.json")
_DEFAULT_OUTPUT = Path("runs/confirmatory_result_manifest.yaml")


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    value = (
        json.loads(text)
        if path.suffix.lower() == ".json"
        else yaml.safe_load(text)
    )
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object/mapping")
    return value


def _repository_commit(explicit: str | None) -> str:
    if explicit:
        value = explicit
    elif os.environ.get("GITHUB_SHA"):
        value = str(os.environ["GITHUB_SHA"])
    else:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
    if (
        len(value) < 7
        or len(value) > 40
        or any(ch not in "0123456789abcdefABCDEF" for ch in value)
    ):
        raise ValueError("repository commit must be a 7-40 character hex SHA")
    return value.lower()


def _jsonl_count(path: Path) -> int:
    count = sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if count < 1:
        raise ValueError(f"{path} contains no records")
    return count


def _artifact(path: Path, count: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path_or_ref": str(path),
        "sha256": _sha256(path),
    }
    if count is not None:
        result["record_count"] = count
    return result


def build_result_manifest(
    *,
    run_plan_path: Path,
    sealed_bundle_path: Path,
    raw_execution_records_path: Path,
    deterministic_baseline_path: Path,
    execution_schema_validation_path: Path,
    execution_audit_path: Path,
    structural_validation_path: Path,
    semantic_verification_path: Path,
    analysis_ready_dataset_path: Path,
    result_manifest_id: str,
    created_at: str,
    repository_commit: str | None = None,
) -> dict[str, Any]:
    run_plan = _load_document(run_plan_path)
    run_plan_sha256 = _sha256(run_plan_path)
    current_commit = _repository_commit(repository_commit)
    if run_plan.get("repository_commit") != current_commit:
        raise ValueError(
            "run plan repository_commit does not match result assembly commit"
        )

    sealed = run_plan.get("sealed_set")
    if not isinstance(sealed, dict):
        raise ValueError("run plan lacks sealed_set binding")
    sealed_bundle_sha256 = _sha256(sealed_bundle_path)
    if sealed.get("bundle_sha256") != sealed_bundle_sha256:
        raise ValueError("sealed bundle bytes do not match run plan")

    raw_count = _jsonl_count(raw_execution_records_path)
    baseline_count = _jsonl_count(deterministic_baseline_path)
    structural_count = _jsonl_count(structural_validation_path)
    semantic_count = _jsonl_count(semantic_verification_path)
    analysis_count = _jsonl_count(analysis_ready_dataset_path)

    schema_report = _load_document(execution_schema_validation_path)
    if schema_report.get("passed") is not True:
        raise ValueError("execution schema validation did not pass")
    if schema_report.get("invalid_record_count") != 0:
        raise ValueError("execution schema validation reports invalid records")
    if schema_report.get("batch_errors") not in ([], None):
        raise ValueError("execution schema validation reports batch errors")
    if schema_report.get("valid_record_count") != raw_count:
        raise ValueError(
            "execution schema-validation valid count does not match raw records"
        )
    if schema_report.get("record_count") != raw_count:
        raise ValueError(
            "execution schema-validation record count does not match raw records"
        )
    if schema_report.get("input_sha256") != _sha256(
        raw_execution_records_path
    ):
        raise ValueError(
            "execution schema-validation input hash does not match raw records"
        )
    frozen = run_plan.get("frozen_artifacts")
    if not isinstance(frozen, dict):
        raise ValueError("run plan lacks frozen_artifacts")
    if schema_report.get("execution_record_schema_sha256") != frozen.get(
        "execution_record_schema_sha256"
    ):
        raise ValueError(
            "execution schema-validation schema hash does not match run plan"
        )

    audit_report = _load_document(execution_audit_path)
    if audit_report.get("complete") is not True:
        raise ValueError("confirmatory execution audit did not pass")
    if audit_report.get("blockers") not in ([], None):
        raise ValueError("confirmatory execution audit still lists blockers")
    if audit_report.get("source_hash_binding_verified") is not True:
        raise ValueError("execution audit did not verify sealed source hashes")
    audit_inputs = audit_report.get("inputs")
    if not isinstance(audit_inputs, dict):
        raise ValueError("execution audit lacks input hash bindings")
    expected_audit_inputs = {
        "run_plan_sha256": run_plan_sha256,
        "execution_records_sha256": _sha256(raw_execution_records_path),
        "deterministic_baseline_sha256": _sha256(
            deterministic_baseline_path
        ),
    }
    for key, expected in expected_audit_inputs.items():
        if audit_inputs.get(key) != expected:
            raise ValueError(f"execution audit input hash mismatch: {key}")

    expected_counts = run_plan.get("expected_execution_counts")
    audit_counts = audit_report.get("counts")
    if not isinstance(expected_counts, dict) or not isinstance(audit_counts, dict):
        raise ValueError("run plan or execution audit counts are missing")
    count_bindings = {
        "provider_call_count": "provider_generation_calls",
        "derived_repair_count": "derived_repair_outputs",
        "deterministic_baseline_count": "deterministic_baseline_outputs",
        "total_arm_output_count": "total_arm_outputs",
    }
    for audit_key, plan_key in count_bindings.items():
        if audit_counts.get(audit_key) != expected_counts.get(plan_key):
            raise ValueError(
                f"execution audit count does not match run plan: {audit_key}"
            )
    if raw_count != (
        int(expected_counts["provider_generation_calls"])
        + int(expected_counts["derived_repair_outputs"])
    ):
        raise ValueError("raw execution record count does not match run plan")
    if baseline_count != int(
        expected_counts["deterministic_baseline_outputs"]
    ):
        raise ValueError("baseline output count does not match run plan")

    result = {
        "schema_version": "0.2.0",
        "result_manifest_id": result_manifest_id,
        "status": "execution_complete_audited",
        "created_at": created_at,
        "repository_commit": current_commit,
        "run_plan_sha256": run_plan_sha256,
        "sealed_bundle_sha256": sealed_bundle_sha256,
        "raw_execution_records": _artifact(
            raw_execution_records_path,
            raw_count,
        ),
        "deterministic_baseline_outputs": _artifact(
            deterministic_baseline_path,
            baseline_count,
        ),
        "execution_schema_validation": {
            **_artifact(execution_schema_validation_path),
            "complete": True,
        },
        "execution_audit": {
            **_artifact(execution_audit_path),
            "complete": True,
        },
        "structural_validation_evidence": _artifact(
            structural_validation_path,
            structural_count,
        ),
        "semantic_verification_evidence": _artifact(
            semantic_verification_path,
            semantic_count,
        ),
        "analysis_ready_dataset": _artifact(
            analysis_ready_dataset_path,
            analysis_count,
        ),
    }

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(result)
    readiness = assess_confirmatory_result_manifest(
        result,
        run_plan=run_plan,
        run_plan_sha256=run_plan_sha256,
    )
    if not readiness.ready:
        raise ValueError(
            "assembled confirmatory result manifest is not ready: "
            + "; ".join(readiness.blockers)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-plan", type=Path, required=True)
    parser.add_argument("--sealed-bundle", type=Path, required=True)
    parser.add_argument("--execution-records", type=Path, required=True)
    parser.add_argument("--deterministic-baseline", type=Path, required=True)
    parser.add_argument(
        "--execution-schema-validation",
        type=Path,
        required=True,
    )
    parser.add_argument("--execution-audit", type=Path, required=True)
    parser.add_argument("--structural-validation", type=Path, required=True)
    parser.add_argument("--semantic-verification", type=Path, required=True)
    parser.add_argument("--analysis-ready-dataset", type=Path, required=True)
    parser.add_argument("--result-manifest-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--repository-commit")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_result_manifest(
        run_plan_path=args.run_plan,
        sealed_bundle_path=args.sealed_bundle,
        raw_execution_records_path=args.execution_records,
        deterministic_baseline_path=args.deterministic_baseline,
        execution_schema_validation_path=args.execution_schema_validation,
        execution_audit_path=args.execution_audit,
        structural_validation_path=args.structural_validation,
        semantic_verification_path=args.semantic_verification,
        analysis_ready_dataset_path=args.analysis_ready_dataset,
        result_manifest_id=args.result_manifest_id,
        created_at=args.created_at,
        repository_commit=args.repository_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(result, sort_keys=False),
        encoding="utf-8",
    )
    print(yaml.safe_dump(result, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
