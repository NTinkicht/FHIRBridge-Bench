"""Build the primary VUR hypothesis preregistration fail-closed."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import jsonschema
import yaml

from fhirbridge.primary_vur_hypothesis import (
    assess_primary_vur_hypothesis,
)

_SCHEMA = Path(
    "analysis/schema/primary_vur_hypothesis_preregistration.schema.json"
)
_DEFAULT_OUTPUT = Path(
    "analysis/primary_vur_hypothesis_preregistration.yaml"
)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the pilot-derived primary VUR threshold and inference "
            "policy before confirmatory inference."
        )
    )
    parser.add_argument("--pilot-case-manifest", type=Path, required=True)
    parser.add_argument("--pilot-analysis", type=Path, required=True)
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--threshold-rationale", required=True)
    parser.add_argument("--inclusion-rule", required=True)
    parser.add_argument("--aggregation-policy", required=True)
    parser.add_argument("--inference-method", required=True)
    parser.add_argument("--cluster-handling", required=True)
    parser.add_argument("--confidence-interval-method", required=True)
    parser.add_argument("--decision-rule", required=True)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    record = {
        "schema_version": "0.1.0",
        "record_id": args.record_id,
        "status": "preregistered",
        "created_at": args.created_at,
        "sealed_set_opened": False,
        "pilot_evidence": {
            "pilot_case_manifest_sha256": _sha256_file(
                args.pilot_case_manifest
            ),
            "pilot_analysis_sha256": _sha256_file(args.pilot_analysis),
        },
        "estimand": {
            "name": "VUR",
            "direction": "FHIR_to_HL7v2",
            "denominator_rule": "VALID_and_semantic_determinate",
        },
        "hypothesis": {
            "null_relation": "VUR_less_than_or_equal_threshold",
            "alternative_relation": "VUR_greater_than_threshold",
            "nontrivial_vur_threshold": args.threshold,
            "threshold_rationale": args.threshold_rationale,
        },
        "target_population": {
            "inclusion_rule": args.inclusion_rule,
            "model_strategy_aggregation_policy": args.aggregation_policy,
            "cluster_id_field": "analysis_cluster_id",
        },
        "inference": {
            "method": args.inference_method,
            "alpha": 0.05,
            "sidedness": "one_sided",
            "cluster_handling": args.cluster_handling,
            "confidence_interval_method": args.confidence_interval_method,
            "decision_rule": args.decision_rule,
        },
        "indeterminate_policy": {
            "semantic_indeterminate_policy": (
                "exclude_from_binary_VUR_with_reported_denominator_loss_and_"
                "sensitivity_bounds"
            ),
            "structural_policy_ref": (
                "benchmark/structural_validity_policy.yaml"
            ),
        },
    }

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(record)

    readiness = assess_primary_vur_hypothesis(record)
    if not readiness.ready:
        raise ValueError(
            "primary VUR hypothesis preregistration is not ready: "
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
