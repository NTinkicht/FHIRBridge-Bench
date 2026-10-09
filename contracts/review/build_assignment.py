"""Build the machine-readable external projectability-review assignment."""

from __future__ import annotations

import json
from pathlib import Path

import fhirbridge.schema_validation
from fhirbridge.contract_review_assignment import build_contract_review_assignment

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"
_CANDIDATES = "contracts/review/relationship_candidates_v0.1.yaml"


def main() -> int:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    candidates = fhirbridge.schema_validation.load_yaml(_CANDIDATES)
    assignment = build_contract_review_assignment(contract, candidates)

    output_dir = Path("contracts/review/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "contract-review-assignment-v0.2.json"
    output.write_text(
        json.dumps(assignment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "assignment_id": assignment["assignment_id"],
                "review_item_count": assignment["review_item_count"],
                "assignment_sha256": assignment["assignment_sha256"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
