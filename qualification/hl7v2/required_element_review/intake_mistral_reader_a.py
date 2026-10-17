"""Private, local Mistral Reader A original-response lock creation.

Never invoke this CLI against public-repository files containing protected
HL7 publication excerpts, private reviewer identity or first-round responses.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fhirbridge.lri_ai_reader_preflight import preflight_mistral_reader_a

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _private(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(_REPOSITORY_ROOT):
        raise ValueError("AI reader input/output must be outside the public repository")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_mistral_yaml", type=Path)
    parser.add_argument("private_lock_output_json", type=Path)
    parser.add_argument(
        "--source-use-authorized",
        action="store_true",
        help=(
            "Coordinator declares that license, hosting and data handling "
            "requirements were checked BEFORE Mistral received the sources"
        ),
    )
    args = parser.parse_args()
    try:
        original = _private(args.original_mistral_yaml)
        destination = _private(args.private_lock_output_json)
        result = preflight_mistral_reader_a(
            original.read_bytes(),
            source_use_authorized=args.source_use_authorized,
        )
        # Exclusive creation avoids rewriting any earlier response-lock receipt.
        # O_NOFOLLOW is available on POSIX and reduces leaf-symlink risk.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(result.original_response_lock, output, sort_keys=True, indent=2)
            output.write("\n")
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 1

    # Do not print the original source clauses or the reviewer submission.
    print(json.dumps({
        "status": result.status,
        "original_response_sha256": result.original_response_sha256,
        "metadata_schema_ready": result.metadata_schema_ready,
        "declared_source_use_authorized_not_independently_verified": True,
        "independent_human_extraction_received": False,
        "requirements_denominator_qualified": False,
        "G1_qualified": False,
        "confirmatory_permission": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
