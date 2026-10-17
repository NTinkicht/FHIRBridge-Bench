"""Build a machine-filled candidate LRI profile freeze record from a ZIP archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fhirbridge.hl7v2_profile_archive import inspect_profile_archive
from fhirbridge.lri_profile_pin import (
    LriAcquisitionMetadata,
    build_lri_profile_pin_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--source-record", required=True)
    parser.add_argument("--export-id", required=True)
    parser.add_argument("--acquired-at", required=True)
    parser.add_argument("--acquired-by-role", required=True)
    parser.add_argument("--redistribution-status", required=True)
    args = parser.parse_args()

    inspection = inspect_profile_archive(args.archive.resolve())
    acquisition = LriAcquisitionMetadata(
        source_url_or_record=args.source_record,
        igamt_export_identifier=args.export_id,
        acquired_at=args.acquired_at,
        acquired_by_role_id=args.acquired_by_role,
        redistribution_status=args.redistribution_status,
    )
    record = build_lri_profile_pin_candidate(inspection, acquisition)

    output_dir = Path("qualification/hl7v2/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "profile-pin-candidate.json"
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
