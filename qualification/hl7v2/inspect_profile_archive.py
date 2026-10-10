"""Inspect a locally acquired IGAMT validation-profile ZIP archive."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fhirbridge.hl7v2_profile_archive import inspect_profile_archive


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python qualification/hl7v2/inspect_profile_archive.py "
            "/path/to/igamt-export.zip"
        )
        return 2

    inspection = inspect_profile_archive(Path(sys.argv[1]).resolve())
    record = {
        "archive_sha256": inspection.archive_sha256,
        "source_directory": inspection.source_directory,
        "aggregate_sha256": inspection.manifest.aggregate_sha256,
        "files": inspection.manifest.to_dict()["files"],
        "identity": {
            "hl7_version": inspection.identity.hl7_version,
            "message_type": inspection.identity.message_type,
            "event_type": inspection.identity.event_type,
            "message_structure": inspection.identity.message_structure,
        },
        "reference_inventory": inspection.reference_inventory.to_dict(),
        "target_reference_signals": inspection.target_reference_signals,
        "selected_message": {
            "identifier": inspection.selected_message.identifier,
            "description": inspection.selected_message.description,
            "message_type": inspection.selected_message.message_type,
            "event_type": inspection.selected_message.event_type,
            "message_structure": inspection.selected_message.message_structure,
        },
    }

    output_dir = Path("qualification/hl7v2/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "candidate-profile-archive-inspection.json"
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
