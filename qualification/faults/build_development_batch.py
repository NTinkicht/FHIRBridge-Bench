"""Build the deterministic pre-freeze development seeded-fault batch."""

from __future__ import annotations

import json
from pathlib import Path

import fhirbridge.schema_validation
from fhirbridge.fault_batch import build_development_fault_batch

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def main() -> int:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    batch = build_development_fault_batch(contract)

    output_dir = Path("qualification/faults/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "development-fault-batch.json"
    output.write_text(
        json.dumps(batch.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": len(batch.cases),
                "class_counts": batch.to_dict()["class_counts"],
                "batch_sha256": batch.batch_sha256,
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
