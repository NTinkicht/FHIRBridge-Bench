"""Validate and compare two independent semantic-mapping reviews."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import jsonschema

from fhirbridge.semantic_mapping_review import (
    mapping_review_pair_to_dict,
    paired_mapping_review_summary,
)

_SCHEMA = Path("contracts/review/semantic_mapping_review_response.schema.json")
_DEFAULT_ASSIGNMENT = Path(
    "contracts/review/generated/semantic-mapping-review-assignment.json"
)
_DEFAULT_OUTPUT = Path(
    "contracts/review/generated/semantic-mapping-review-pair-report.json"
)


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical_sha256(document: dict) -> str:
    data = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reviewer_a", type=Path)
    parser.add_argument("reviewer_b", type=Path)
    parser.add_argument(
        "--assignment",
        type=Path,
        default=_DEFAULT_ASSIGNMENT,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
    )
    args = parser.parse_args()

    assignment = _load_json(args.assignment)
    first = _load_json(args.reviewer_a)
    second = _load_json(args.reviewer_b)
    schema = _load_json(_SCHEMA)

    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(first)
    validator.validate(second)

    summary = paired_mapping_review_summary(
        assignment,
        first,
        second,
    )
    report = mapping_review_pair_to_dict(summary)
    report.update(
        {
            "schema_version": "0.1.0",
            "reviewer_a_response_sha256": _canonical_sha256(first),
            "reviewer_b_response_sha256": _canonical_sha256(second),
            "original_reviews_preserved": True,
            "assignment_sha256": _canonical_sha256(assignment),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
