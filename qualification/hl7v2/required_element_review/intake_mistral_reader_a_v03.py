"""Locally preserve isolated Mistral AI v0.3 rule-level original evidence.

Requires prior permission for any HL7 source processing by the Mistral
service. This utility never contacts an LLM or opens official source PDFs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fhirbridge.lri_ai_reader_v03 import preflight_mistral_reader_a_v03

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _outside_repo(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(_REPO_ROOT):
        raise ValueError("v0.3 original and receipt must stay outside the public repository")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_mistral_v03_yaml", type=Path)
    parser.add_argument("private_v03_lock_output_json", type=Path)
    parser.add_argument(
        "--source-use-authorized",
        action="store_true",
        help="Coordinator has checked the licensing, hosting and data-handling obligations",
    )
    options = parser.parse_args()
    try:
        source = _outside_repo(options.original_mistral_v03_yaml)
        destination = _outside_repo(options.private_v03_lock_output_json)
        if source == destination:
            raise ValueError("original v0.3 submission and receipt must be different files")
        result = preflight_mistral_reader_a_v03(
            source.read_bytes(), source_use_authorized=options.source_use_authorized
        )
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(result.original_response_lock, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        # Error details are technical; never print original source data.
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 1

    print(json.dumps({
        "status": result.status,
        "original_response_sha256": result.original_response_sha256,
        "metadata_schema_ready": result.metadata_schema_ready,
        "source_use_authorized_only_by_coordinator_declaration": True,
        "independent_human_extraction_received": False,
        "requirements_denominator_qualified": False,
        "G1_qualified": False,
        "confirmatory_permission": False,
    }, sort_keys=True))
    # An exposure is still locked privately, but is never successful intake.
    return 0 if result.status == "PRIVATE_AI_V03_RULE_LEVEL_NOT_HUMAN_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
