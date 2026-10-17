"""Build a schema-valid pilot acceptance preregistration from evidence files."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from fhirbridge.pilot_acceptance import (
    assess_pilot_acceptance_preregistration,
)
from fhirbridge.pilot_record import build_pilot_acceptance_record

_SCHEMA = Path(
    "expert_validation/schema/pilot_acceptance_preregistration.schema.json"
)
_DEFAULT_OUTPUT = Path(
    "expert_validation/pilot_acceptance_preregistration.yaml"
)


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _load_list(path: Path, label: str) -> list[dict[str, Any]]:
    value = _load(path)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty JSON/YAML list")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must contain objects only")
    return list(value)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _sha256_arg(value: str, name: str) -> str:
    lowered = value.lower()
    if (
        len(lowered) != 64
        or any(character not in "0123456789abcdef" for character in lowered)
    ):
        raise ValueError(f"{name} must be a 64-character SHA-256 digest")
    return lowered


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the pilot-derived verifier acceptance preregistration "
            "before sealed-set opening."
        )
    )
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--verifier-results", type=Path, required=True)
    parser.add_argument("--pilot-case-manifest", type=Path, required=True)
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--verifier-sha256", required=True)
    parser.add_argument("--projectability-contract-sha256", required=True)

    parser.add_argument("--minimum-sensitivity", type=float, required=True)
    parser.add_argument(
        "--sensitivity-statistic",
        choices=["point_estimate", "lower_95_percent_confidence_bound"],
        required=True,
    )
    parser.add_argument("--sensitivity-rationale", required=True)

    parser.add_argument("--minimum-ppv", type=float, required=True)
    parser.add_argument(
        "--ppv-statistic",
        choices=["point_estimate", "lower_95_percent_confidence_bound"],
        required=True,
    )
    parser.add_argument("--ppv-rationale", required=True)

    parser.add_argument(
        "--maximum-runtime-indeterminate-rate",
        type=float,
        required=True,
    )
    parser.add_argument(
        "--indeterminate-statistic",
        choices=["point_estimate", "upper_95_percent_confidence_bound"],
        required=True,
    )
    parser.add_argument("--indeterminate-rationale", required=True)
    parser.add_argument("--sampling-notes")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    adjudications = _load_list(args.adjudications, "adjudications")
    verifier_results = _load_list(args.verifier_results, "verifier results")

    record = build_pilot_acceptance_record(
        adjudications=adjudications,
        verifier_results=verifier_results,
        record_id=args.record_id,
        created_at=args.created_at,
        pilot_case_manifest_sha256=_sha256_file(args.pilot_case_manifest),
        repository_commit=args.repository_commit,
        verifier_sha256=_sha256_arg(
            args.verifier_sha256,
            "verifier-sha256",
        ),
        projectability_contract_sha256=_sha256_arg(
            args.projectability_contract_sha256,
            "projectability-contract-sha256",
        ),
        minimum_sensitivity=args.minimum_sensitivity,
        sensitivity_statistic=args.sensitivity_statistic,
        sensitivity_rationale=args.sensitivity_rationale,
        minimum_ppv=args.minimum_ppv,
        ppv_statistic=args.ppv_statistic,
        ppv_rationale=args.ppv_rationale,
        maximum_runtime_indeterminate_rate=(
            args.maximum_runtime_indeterminate_rate
        ),
        indeterminate_statistic=args.indeterminate_statistic,
        indeterminate_rationale=args.indeterminate_rationale,
        sampling_enrichment_or_weighting_notes=args.sampling_notes,
    )

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(record)

    readiness = assess_pilot_acceptance_preregistration(record)
    if not readiness.ready:
        raise ValueError(
            "pilot acceptance preregistration is not freeze-ready: "
            + "; ".join(readiness.blockers)
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(record, sort_keys=False),
        encoding="utf-8",
    )
    print(yaml.safe_dump(record, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
