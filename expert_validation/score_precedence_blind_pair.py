"""Validate two independent precedence responses and seed adjudication."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import jsonschema
import yaml

from fhirbridge.precedence_blind_review import (
    build_precedence_adjudication_seed,
    compare_precedence_responses,
)

_SCHEMA = Path("expert_validation/schema/precedence_blind_response.schema.json")
_CANDIDATE = Path("benchmark/error_precedence_policy_candidate.yaml")
_DEFAULT_REPORT = Path(
    "expert_validation/generated/precedence-blind-pair-report.json"
)
_DEFAULT_SEED = Path(
    "expert_validation/generated/precedence-adjudication-seed.yaml"
)


def _json(path: Path) -> dict:
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
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    parser.add_argument("--adjudication-seed", type=Path, default=_DEFAULT_SEED)
    args = parser.parse_args()

    first = _json(args.reviewer_a)
    second = _json(args.reviewer_b)
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(first)
    validator.validate(second)

    pair = compare_precedence_responses(first, second)
    first_hash = _canonical_sha256(first)
    second_hash = _canonical_sha256(second)
    report = {
        "schema_version": "0.1.0",
        **pair,
        "reviewer_a_response_sha256": first_hash,
        "reviewer_b_response_sha256": second_hash,
        "original_responses_preserved": True,
    }
    seed = build_precedence_adjudication_seed(
        first,
        second,
        candidate_policy_sha256=sha256(_CANDIDATE.read_bytes()).hexdigest(),
        reviewer_a_response_sha256=first_hash,
        reviewer_b_response_sha256=second_hash,
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.adjudication_seed.parent.mkdir(parents=True, exist_ok=True)
    args.adjudication_seed.write_text(
        yaml.safe_dump(seed, sort_keys=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
