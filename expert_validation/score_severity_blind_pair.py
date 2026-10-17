"""Validate and combine two blind severity-calibration responses."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import jsonschema
import yaml

from fhirbridge.severity_blind_review import (
    build_severity_adjudication_seed,
    paired_blind_severity_summary,
)

_SCHEMA = Path("expert_validation/schema/severity_blind_response.schema.json")
_ANCHORS = Path("expert_validation/severity_anchor_set.yaml")
_CANDIDATE = Path("benchmark/severity_policy_candidate.yaml")
_DEFAULT_REPORT = Path(
    "expert_validation/generated/severity-blind-pair-report.json"
)
_DEFAULT_SEED = Path(
    "expert_validation/generated/severity-adjudication-seed.yaml"
)


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def _canonical_sha256(document: dict) -> str:
    data = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reviewer_a", type=Path)
    parser.add_argument("reviewer_b", type=Path)
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    parser.add_argument("--adjudication-seed", type=Path, default=_DEFAULT_SEED)
    args = parser.parse_args()

    first = _json(args.reviewer_a)
    second = _json(args.reviewer_b)
    schema = _json(_SCHEMA)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(first)
    validator.validate(second)

    anchors = _yaml(_ANCHORS)
    summary = paired_blind_severity_summary(first, second, anchors)
    first_hash = _canonical_sha256(first)
    second_hash = _canonical_sha256(second)

    report = {
        "schema_version": "0.1.0",
        "assignment_id": summary.assignment_id,
        "reviewer_a_id": summary.reviewer_a_id,
        "reviewer_b_id": summary.reviewer_b_id,
        "reviewer_a_response_sha256": first_hash,
        "reviewer_b_response_sha256": second_hash,
        "anchor_ids": list(summary.anchor_ids),
        "anchor_count": len(summary.anchor_ids),
        "exact_agreement_count": summary.exact_agreement_count,
        "exact_agreement_rate": summary.exact_agreement_rate,
        "disagreement_anchor_ids": list(summary.disagreement_anchor_ids),
        "disagreements": [
            {
                "anchor_id": item.anchor_id,
                "reviewer_a_severity": item.reviewer_a_severity,
                "reviewer_b_severity": item.reviewer_b_severity,
            }
            for item in summary.disagreements
        ],
        "adjudication_performed": False,
        "original_responses_preserved": True,
    }
    seed = build_severity_adjudication_seed(
        first,
        second,
        anchors,
        candidate_policy_sha256=_file_sha256(_CANDIDATE),
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
