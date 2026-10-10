"""Validate confirmatory model-execution JSONL against the frozen schema."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import jsonschema

_DEFAULT_SCHEMA = Path("models/schema/model_execution_record.schema.json")
_DEFAULT_OUTPUT = Path("runs/results/execution-schema-validation.json")


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_jsonl(
    input_path: Path,
    schema_path: Path = _DEFAULT_SCHEMA,
) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    record_count = 0
    invalid_records: list[dict[str, object]] = []
    seen_execution_ids: set[str] = set()

    for line_number, raw_line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        record_count += 1
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid_records.append(
                {
                    "line_number": line_number,
                    "execution_id": None,
                    "errors": [f"invalid JSON: {exc.msg}"],
                }
            )
            continue
        if not isinstance(value, dict):
            invalid_records.append(
                {
                    "line_number": line_number,
                    "execution_id": None,
                    "errors": ["record must be a JSON object"],
                }
            )
            continue

        execution_id = value.get("execution_id")
        duplicate = (
            isinstance(execution_id, str)
            and execution_id in seen_execution_ids
        )
        if isinstance(execution_id, str):
            seen_execution_ids.add(execution_id)

        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: list(error.absolute_path),
        )
        messages = [
            (
                f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: "
                f"{error.message}"
            )
            for error in errors
        ]
        if duplicate:
            messages.append("execution_id is duplicated within the JSONL batch")
        if messages:
            invalid_records.append(
                {
                    "line_number": line_number,
                    "execution_id": (
                        execution_id if isinstance(execution_id, str) else None
                    ),
                    "errors": messages,
                }
            )

    if record_count == 0:
        invalid_records.append(
            {
                "line_number": None,
                "execution_id": None,
                "errors": ["execution JSONL contains no records"],
            }
        )

    invalid_count = len(invalid_records)
    return {
        "schema_version": "0.1.0",
        "input_path": str(input_path),
        "input_sha256": _sha256(input_path),
        "execution_record_schema_path": str(schema_path),
        "execution_record_schema_sha256": _sha256(schema_path),
        "execution_record_schema_version": schema.get("properties", {})
        .get("schema_version", {})
        .get("const"),
        "record_count": record_count,
        "valid_record_count": record_count - invalid_count,
        "invalid_record_count": invalid_count,
        "duplicate_execution_ids_checked": True,
        "invalid_records": invalid_records,
        "passed": invalid_count == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--schema", type=Path, default=_DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = validate_jsonl(args.input, args.schema)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
