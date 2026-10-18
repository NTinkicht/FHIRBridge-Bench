"""Audit bytes of one developer-only synthetic control pair; never certify G1."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fhirbridge.path_b_control_artifact_binding import bind_unrun_control_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify an unrun Path B synthetic field mutation against exact bytes."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rule-record", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--negative", type=Path, required=True)
    args = parser.parse_args()

    proof = bind_unrun_control_artifacts(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        rule=json.loads(args.rule_record.read_text(encoding="utf-8")),
        positive_bytes=args.positive.read_bytes(),
        negative_bytes=args.negative.read_bytes(),
    )
    output = asdict(proof) | {
        "status": proof.status,
        "G1_qualified": proof.G1_qualified,
        "validator_expected_locus_failure_confirmed": (
            proof.validator_expected_locus_failure_confirmed
        ),
        "confirmatory_permission": proof.confirmatory_permission,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
