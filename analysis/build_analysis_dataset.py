"""Build the confirmatory no-silent-exclusion analysis dataset."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.analysis_dataset import build_analysis_rows

_STRUCTURAL_SCHEMA = Path(
    "analysis/schema/structural_evidence_record.schema.json"
)
_SEMANTIC_SCHEMA = Path(
    "analysis/schema/semantic_evidence_record.schema.json"
)
_ROW_SCHEMA = Path("analysis/schema/analysis_row.schema.json")
_DEFAULT_OUTPUT = Path("runs/results/analysis-rows.jsonl")
_DEFAULT_REPORT = Path("runs/results/analysis-dataset-build.json")


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


def _load_jsonl_validated(
    path: Path,
    schema_path: Path,
) -> list[dict[str, Any]]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
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
            raise ValueError(f"{path}:{line_number} must be a JSON object")
        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            raise ValueError(
                f"{path}:{line_number} fails schema: "
                + "; ".join(error.message for error in errors)
            )
        records.append(value)
    if not records:
        raise ValueError(f"{path} contains no records")
    return records


def build_dataset(
    *,
    run_plan_path: Path,
    sealed_case_manifest_path: Path,
    structural_evidence_path: Path,
    semantic_evidence_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run_plan = _load_document(run_plan_path)
    sealed_manifest = _load_document(sealed_case_manifest_path)

    sealed = run_plan.get("sealed_set")
    if not isinstance(sealed, dict):
        raise ValueError("run plan lacks sealed_set binding")
    manifest_sha = _sha256(sealed_case_manifest_path)
    if sealed.get("case_manifest_sha256") != manifest_sha:
        raise ValueError(
            "sealed case manifest bytes do not match confirmatory run plan"
        )

    model_keys = run_plan.get("model_keys")
    if not isinstance(model_keys, list):
        raise ValueError("run plan lacks model_keys")

    structural = _load_jsonl_validated(
        structural_evidence_path,
        _STRUCTURAL_SCHEMA,
    )
    semantic = _load_jsonl_validated(
        semantic_evidence_path,
        _SEMANTIC_SCHEMA,
    )

    expected_counts = run_plan.get("expected_execution_counts")
    if not isinstance(expected_counts, dict):
        raise ValueError("run plan lacks expected_execution_counts")
    expected_arm_outputs = expected_counts.get("total_arm_outputs")
    if len(structural) != expected_arm_outputs:
        raise ValueError(
            "structural evidence count does not match run-plan arm outputs"
        )
    if len(semantic) != expected_arm_outputs:
        raise ValueError(
            "semantic evidence count does not match run-plan arm outputs"
        )

    rows = build_analysis_rows(
        sealed_case_manifest=sealed_manifest,
        model_keys=[str(value) for value in model_keys],
        structural_records=structural,
        semantic_records=semantic,
    )

    case_count = sealed.get("case_count")
    expected_rows = (
        case_count * len(model_keys)
        if isinstance(case_count, int)
        and not isinstance(case_count, bool)
        else None
    )
    if expected_rows is None or len(rows) != expected_rows:
        raise ValueError("analysis row count does not equal N*M")

    row_schema = json.loads(_ROW_SCHEMA.read_text(encoding="utf-8"))
    row_validator = jsonschema.Draft202012Validator(row_schema)
    for index, row in enumerate(rows, start=1):
        errors = list(row_validator.iter_errors(row))
        if errors:
            raise ValueError(
                f"analysis row {index} fails schema: "
                + "; ".join(error.message for error in errors)
            )

    report = {
        "schema_version": "0.1.0",
        "run_plan_sha256": _sha256(run_plan_path),
        "sealed_case_manifest_sha256": manifest_sha,
        "structural_evidence_sha256": _sha256(structural_evidence_path),
        "semantic_evidence_sha256": _sha256(semantic_evidence_path),
        "structural_record_count": len(structural),
        "semantic_record_count": len(semantic),
        "analysis_row_count": len(rows),
        "expected_analysis_row_count": expected_rows,
        "no_silent_exclusion_verified": True,
    }
    return rows, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-plan", type=Path, required=True)
    parser.add_argument("--sealed-case-manifest", type=Path, required=True)
    parser.add_argument("--structural-evidence", type=Path, required=True)
    parser.add_argument("--semantic-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    args = parser.parse_args()

    rows, report = build_dataset(
        run_plan_path=args.run_plan,
        sealed_case_manifest_path=args.sealed_case_manifest,
        structural_evidence_path=args.structural_evidence,
        semantic_evidence_path=args.semantic_evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    report["analysis_dataset_sha256"] = _sha256(args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
