"""Inspect and hash a candidate IGAMT LRI profile bundle before validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fhirbridge.hl7v2_profile_bundle import (
    assert_single_oru_r01_profile,
    compute_profile_bundle_manifest,
    inspect_profile_identity,
    inspect_profile_messages,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python qualification/hl7v2/inspect_profile.py "
            "/path/to/IGAMT_bundle_directory"
        )
        return 2

    root = Path(sys.argv[1]).resolve()
    manifest = compute_profile_bundle_manifest(root)
    identity = inspect_profile_identity(root)
    selected = assert_single_oru_r01_profile(root)
    messages = inspect_profile_messages(root)

    record = {
        "local_directory": str(root),
        "aggregate_sha256": manifest.aggregate_sha256,
        "files": manifest.to_dict()["files"],
        "identity": {
            "hl7_version": identity.hl7_version,
            "message_type": identity.message_type,
            "event_type": identity.event_type,
            "message_structure": identity.message_structure,
        },
        "selected_message": {
            "identifier": selected.identifier,
            "description": selected.description,
            "message_type": selected.message_type,
            "event_type": selected.event_type,
            "message_structure": selected.message_structure,
        },
        "message_count": len(messages),
    }

    output_dir = Path("qualification/hl7v2/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "candidate-profile-inspection.json"
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
