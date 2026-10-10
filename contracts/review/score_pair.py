"""Validate and score one pair of external projectability-contract reviews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fhirbridge.contract_review_report import build_contract_review_pair_report
from fhirbridge.schema_validation import load_yaml, require_valid_document

_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_CANDIDATES = Path("contracts/review/relationship_candidates_v0.2.yaml")
_SCHEMA = Path("contracts/review/contract_review_blind_response.schema.json")
_DEFAULT_OUTPUT = Path(
    "contracts/review/generated/contract-review-pair-report-v0.3-blind.json"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate two independent blind Stage-1 contract-review responses "
            "and write agreement/disagreement evidence without adjudicating them."
        )
    )
    parser.add_argument("reviewer_a", type=Path)
    parser.add_argument("reviewer_b", type=Path)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    require_valid_document(args.reviewer_a, _SCHEMA)
    require_valid_document(args.reviewer_b, _SCHEMA)

    response_a = load_yaml(args.reviewer_a)
    response_b = load_yaml(args.reviewer_b)
    contract = load_yaml(_CONTRACT)
    candidates = load_yaml(_CANDIDATES)

    report = build_contract_review_pair_report(
        response_a,
        response_b,
        contract=contract,
        relationship_candidates=candidates,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output": str(args.output),
                "rule_count": report["rule_count"],
                "raw_agreement": report["agreement"]["raw_agreement"],
                "cohens_kappa": report["agreement"]["cohens_kappa"],
                "gwets_ac1": report["agreement"]["gwets_ac1"],
                "disagreement_count": report["disagreement_count"],
                "adjudication_required": report["adjudication_required"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
