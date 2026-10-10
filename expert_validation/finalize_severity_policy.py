"""Finalize the semantic severity policy from a completed calibration record."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.severity_calibration import assess_severity_calibration

_SCHEMA = Path("expert_validation/schema/severity_calibration.schema.json")
_DEFAULT_CANDIDATE = Path("benchmark/severity_policy_candidate.yaml")
_DEFAULT_OUTPUT = Path("benchmark/severity_policy_frozen.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def finalize_severity_policy(
    *,
    candidate_path: Path,
    calibration_path: Path,
    calibration_ref: str,
) -> dict[str, Any]:
    candidate = _load_yaml(candidate_path)
    calibration = _load_yaml(calibration_path)

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(calibration)
    readiness = assess_severity_calibration(calibration)
    if not readiness.ready:
        raise ValueError(
            "severity calibration is not freeze-ready: "
            + "; ".join(readiness.blockers)
        )

    candidate_hash = _sha256(candidate_path)
    if calibration.get("candidate_policy_sha256") != candidate_hash:
        raise ValueError(
            "severity calibration was not performed against this candidate policy"
        )

    header = candidate.get("severity_policy")
    if not isinstance(header, dict):
        raise ValueError("candidate severity policy metadata is missing")
    if header.get("status") == "frozen":
        raise ValueError("candidate severity policy is already marked frozen")

    decision = calibration["major_threshold_decision"]
    levels = candidate.get("levels")
    if not isinstance(levels, dict):
        raise ValueError("candidate severity levels are missing")

    frozen = deepcopy(candidate)
    frozen_header = frozen["severity_policy"]
    frozen_header["version"] = "1.0.0"
    frozen_header["status"] = "frozen"
    frozen_header["frozen_from_candidate_version"] = header.get("version")
    frozen_header["frozen_from_candidate_sha256"] = candidate_hash

    major = frozen["primary_endpoint_major_candidate"]
    major["levels"] = list(decision["included_levels"])
    major["status"] = "frozen"
    major["threshold"] = decision["threshold"]
    major["expert_calibration_rationale"] = decision["rationale"]

    frozen["expert_calibration"] = {
        "status": "completed",
        "record_ref": calibration_ref,
        "record_sha256": _sha256(calibration_path),
        "candidate_policy_sha256": candidate_hash,
        "calibration_id": calibration["calibration_id"],
        "reviewer_count": len(calibration["reviewers"]),
        "anchor_count": len(calibration["anchor_reviews"]),
        "pre_adjudication_exact_agreement_rate": calibration[
            "pre_adjudication_agreement"
        ]["exact_agreement_rate"],
    }

    # Definitions are measurement anchors and must not be rewritten during
    # finalization. The only semantic choice imported from calibration is the
    # frozen major-threshold decision.
    if frozen["levels"] != levels:
        raise ValueError("severity level definitions changed during finalization")
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=_DEFAULT_CANDIDATE)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--calibration-ref", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = finalize_severity_policy(
        candidate_path=args.candidate,
        calibration_path=args.calibration,
        calibration_ref=args.calibration_ref,
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
