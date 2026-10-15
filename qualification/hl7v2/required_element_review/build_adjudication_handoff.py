"""Build a private, unadjudicated packet from two locked extraction responses.

Example (coordinator only, never in CI with real reviewer data):
  python qualification/hl7v2/required_element_review/build_adjudication_handoff.py \
      reviewer-A.yaml reviewer-A.lock.json \
      reviewer-B.yaml reviewer-B.lock.json adjudication-handoff.json

The output contains reviewer-provided claims and references; retain in
access-controlled storage. This utility does not qualify any standards rules.
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from fhirbridge.lri_adjudication_handoff import build_adjudication_handoff


def _read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("response lock file must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response_a", type=Path)
    parser.add_argument("lock_a", type=Path)
    parser.add_argument("response_b", type=Path)
    parser.add_argument("lock_b", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        output = build_adjudication_handoff(
            args.response_a.read_bytes(),
            _read_object(args.lock_a),
            args.response_b.read_bytes(),
            _read_object(args.lock_b),
        )
        # Never overwrite first-round materials or previously built packets.
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(output, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 1

    print(json.dumps({
        "status": output["status"],
        "packet_sha256": sha256(args.output.read_bytes()).hexdigest(),
        "observed_union_counts": output["observed_union_counts"],
        "standards_completeness_certified": False,
        "G1_qualified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
