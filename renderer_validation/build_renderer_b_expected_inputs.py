"""Build the custodian-side immutable input identity for Renderer B."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import yaml

from fhirbridge.renderer_b_challenge import (
    build_renderer_b_challenge,
    challenge_manifest,
)

_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_OUTPUT = Path(
    "renderer_validation/generated/renderer-b-expected-inputs.yaml"
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--starting-commit",
        required=True,
        help="40-character renderer-b-cleanroom commit handed to implementer.",
    )
    parser.add_argument(
        "--created-at",
        help="ISO-8601 handoff timestamp; defaults to current UTC time.",
    )
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    return parser.parse_args()


def build_record(*, starting_commit: str, created_at: str) -> dict:
    normalized_commit = starting_commit.lower()
    if (
        len(normalized_commit) != 40
        or any(ch not in "0123456789abcdef" for ch in normalized_commit)
        or set(normalized_commit) <= {"0"}
    ):
        raise ValueError("starting_commit must be a nonzero 40-character SHA")

    manifest = challenge_manifest(build_renderer_b_challenge())
    return {
        "schema_version": "0.1.0",
        "handoff_id": "FHIRBRIDGE-RENDERER-B-HANDOFF-001",
        "created_at": created_at,
        "clean_room_inputs": {
            "repository_full_name": "NTinkicht/FHIRBridge-Bench",
            "branch": "renderer-b-cleanroom",
            "starting_commit": normalized_commit,
            "challenge_id": manifest["challenge_id"],
            "challenge_version": manifest["version"],
            "challenge_manifest_sha256": manifest["manifest_sha256"],
            "contract_path": str(_CONTRACT),
            "contract_sha256": _sha256(_CONTRACT),
        },
    }


def main() -> int:
    args = _parse_args()
    created_at = args.created_at or datetime.now(timezone.utc).isoformat()
    record = build_record(
        starting_commit=args.starting_commit,
        created_at=created_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(record, sort_keys=False),
        encoding="utf-8",
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
