"""Capture or verify original Path B reviewer responses without changing bytes.

Use in a PRIVATE coordinator workspace, not the public repository.
  python qualification/hl7v2/required_element_review/lock_responses.py lock A.yaml A.lock.json
  python qualification/hl7v2/required_element_review/lock_responses.py compare \
      A.yaml A.lock.json B.yaml B.lock.json comparison.json
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from fhirbridge.lri_extraction_lock import (
    compare_locked_extractions,
    create_response_lock,
)
from fhirbridge.lri_lock_json import load_coordinator_lock_json


def _json(path: Path) -> dict:
    return load_coordinator_lock_json(path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="mode", required=True)
    lock = subs.add_parser("lock")
    lock.add_argument("response", type=Path)
    lock.add_argument("lock_output", type=Path)
    compare = subs.add_parser("compare")
    compare.add_argument("response_a", type=Path)
    compare.add_argument("lock_a", type=Path)
    compare.add_argument("response_b", type=Path)
    compare.add_argument("lock_b", type=Path)
    compare.add_argument("comparison_output", type=Path)
    args = parser.parse_args()

    # Write with exclusive creation: never overwrite first-round evidence.
    try:
        if args.mode == "lock":
            report = create_response_lock(args.response.read_bytes())
            destination = args.lock_output
        else:
            report = compare_locked_extractions(
                args.response_a.read_bytes(),
                _json(args.lock_a),
                args.response_b.read_bytes(),
                _json(args.lock_b),
            )
            destination = args.comparison_output
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 1

    print(json.dumps({
        "status": report["status"],
        "record_sha256": sha256(destination.read_bytes()).hexdigest(),
        "G1_qualified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
