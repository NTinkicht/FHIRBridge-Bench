"""Audit confirmatory execution completeness and frozen source provenance."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from fhirbridge.confirmatory_execution_audit import audit_confirmatory_execution
from fhirbridge.sealed_case_manifest import (
    sealed_case_ids,
    source_input_sha256_by_case,
)

_DEFAULT_OUTPUT = Path("runs/results/execution-audit.json")


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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(
                f"{path}:{line_number} must contain a JSON object"
            )
        records.append(value)
    if not records:
        raise ValueError(f"{path} contains no records")
    return records


def _baseline_case_ids(path: Path) -> set[str]:
    records = _load_jsonl(path)
    result: set[str] = set()
    for index, record in enumerate(records, start=1):
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(
                f"baseline record {index} lacks a non-empty case_id"
            )
        if case_id in result:
            raise ValueError(
                f"duplicate deterministic baseline case_id: {case_id}"
            )
        result.add(case_id)
    return result


def build_execution_audit(
    *,
    run_plan_path: Path,
    sealed_case_manifest_path: Path,
    execution_records_path: Path,
    deterministic_baseline_path: Path,
) -> dict[str, Any]:
    run_plan = _load_document(run_plan_path)
    sealed_manifest = _load_document(sealed_case_manifest_path)
    records = _load_jsonl(execution_records_path)
    case_ids = sealed_case_ids(sealed_manifest)
    source_hashes = source_input_sha256_by_case(sealed_manifest)
    baseline_case_ids = _baseline_case_ids(deterministic_baseline_path)

    result = audit_confirmatory_execution(
        run_plan,
        records,
        sealed_case_ids=case_ids,
        deterministic_baseline_case_ids=baseline_case_ids,
        expected_source_input_sha256=source_hashes,
    )
    return {
        "schema_version": "0.1.0",
        "complete": result.complete,
        "blockers": list(result.blockers),
        "inputs": {
            "run_plan_sha256": _sha256(run_plan_path),
            "sealed_case_manifest_sha256": _sha256(
                sealed_case_manifest_path
            ),
            "execution_records_sha256": _sha256(execution_records_path),
            "deterministic_baseline_sha256": _sha256(
                deterministic_baseline_path
            ),
        },
        "counts": {
            "provider_call_count": result.provider_call_count,
            "derived_repair_count": result.derived_repair_count,
            "deterministic_baseline_count": result.deterministic_baseline_count,
            "total_arm_output_count": result.total_arm_output_count,
            "outcome_counts": result.outcome_counts,
        },
        "source_hash_binding_verified": result.complete,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-plan", type=Path, required=True)
    parser.add_argument("--sealed-case-manifest", type=Path, required=True)
    parser.add_argument("--execution-records", type=Path, required=True)
    parser.add_argument("--deterministic-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_execution_audit(
        run_plan_path=args.run_plan,
        sealed_case_manifest_path=args.sealed_case_manifest,
        execution_records_path=args.execution_records,
        deterministic_baseline_path=args.deterministic_baseline,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
