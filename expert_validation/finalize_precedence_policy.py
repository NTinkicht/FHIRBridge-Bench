"""Finalize the error-precedence policy from an accepted review."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.precedence_review import assess_precedence_review

_SCHEMA = Path("expert_validation/schema/precedence_review.schema.json")
_DEFAULT_CANDIDATE = Path("benchmark/error_precedence_policy_candidate.yaml")
_DEFAULT_OUTPUT = Path("benchmark/error_precedence_policy_frozen.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def finalize_precedence_policy(
    *,
    candidate_path: Path,
    review_path: Path,
    review_ref: str,
) -> dict[str, Any]:
    candidate = _load_yaml(candidate_path)
    review = _load_yaml(review_path)

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(review)
    readiness = assess_precedence_review(review)
    if not readiness.complete:
        raise ValueError(
            "precedence review is not complete: "
            + "; ".join(readiness.blockers)
        )
    if not readiness.accepted:
        raise ValueError(
            "precedence review did not accept the candidate policy; "
            "revise the candidate and perform a fresh independent review"
        )

    candidate_hash = _sha256(candidate_path)
    if review.get("candidate_policy_sha256") != candidate_hash:
        raise ValueError(
            "precedence review was not performed against this candidate policy"
        )

    header = candidate.get("precedence_policy")
    if not isinstance(header, dict):
        raise ValueError("candidate precedence policy metadata is missing")
    if header.get("status") == "frozen":
        raise ValueError("candidate precedence policy is already frozen")

    frozen = deepcopy(candidate)
    frozen_header = frozen["precedence_policy"]
    frozen_header["version"] = "1.0.0"
    frozen_header["status"] = "frozen"
    frozen_header["frozen_from_candidate_version"] = header.get("version")
    frozen_header["frozen_from_candidate_sha256"] = candidate_hash
    frozen["expert_review"] = {
        "status": "completed",
        "review_ref": review_ref,
        "review_sha256": _sha256(review_path),
        "candidate_policy_sha256": candidate_hash,
        "review_id": review["review_id"],
        "reviewer_count": len(review["reviewers"]),
        "initial_agreement": readiness.initial_agreement,
        "adjudicated_decision": review["adjudication"]["decision"],
        "blind_assignment_id": review["blind_stage_evidence"][
            "assignment_id"
        ],
        "reviewer_a_response_sha256": review["blind_stage_evidence"][
            "reviewer_a_response_sha256"
        ],
        "reviewer_b_response_sha256": review["blind_stage_evidence"][
            "reviewer_b_response_sha256"
        ],
        "other_reviewer_decisions_hidden_initially": review[
            "blind_stage_evidence"
        ]["other_reviewer_decisions_hidden_initially"],
    }
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=_DEFAULT_CANDIDATE)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--review-ref", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = finalize_precedence_policy(
        candidate_path=args.candidate,
        review_path=args.review,
        review_ref=args.review_ref,
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
