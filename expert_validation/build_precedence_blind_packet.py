"""Build an independent error-precedence review packet."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

_POLICY = Path("benchmark/error_precedence_policy_candidate.yaml")
_SCHEMA = Path("expert_validation/schema/precedence_blind_response.schema.json")
_OUTPUT_DIR = Path("expert_validation/generated")
_PACKET = _OUTPUT_DIR / "precedence-review-stage1-independent.zip"
_MANIFEST = _OUTPUT_DIR / "precedence-review-stage1-independent-manifest.json"


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def _readme() -> str:
    return """FHIRBridge-Bench independent semantic error-precedence review

Purpose
-------
Review the supplied candidate precedence policy for cases where one erroneous
target assertion may appear to fit more than one semantic error class.

Choose ACCEPT, REJECT, or INDETERMINATE and explain the decision.

This is an independent initial review. Do not consult the other reviewer before
submitting your response. Do not use sealed benchmark cases, converter outputs,
or verifier outputs as evidence that the proposed order is correct.

Your original response will be retained and hashed before any adjudication.
"""


def build_packet() -> dict[str, object]:
    policy = _load_yaml(_POLICY)
    assignment = {
        "assignment_id": "FHIRBRIDGE-PRECEDENCE-BLIND-001",
        "schema_version": "0.1.0",
        "review_stage": "independent_initial_decision",
        "candidate_policy": policy,
        "response_schema": str(_SCHEMA),
        "other_reviewer_decision_disclosed": False,
    }
    assignment_bytes = (
        json.dumps(assignment, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    schema_bytes = _SCHEMA.read_bytes()
    readme_bytes = _readme().encode("utf-8")

    payloads = {
        "assignment.json": assignment_bytes,
        "response-schema.json": schema_bytes,
        "README.txt": readme_bytes,
    }
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(_PACKET, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(payloads):
            archive.writestr(name, payloads[name])

    manifest = {
        "packet_id": "FHIRBRIDGE-PRECEDENCE-STAGE1-PACKET-001",
        "review_stage": "independent_initial_decision",
        "candidate_policy_sha256": sha256(_POLICY.read_bytes()).hexdigest(),
        "packet_sha256": _sha(_PACKET.read_bytes()),
        "assignment_sha256": _sha(assignment_bytes),
        "other_reviewer_decision_included": False,
        "sealed_case_content_included": False,
        "contents": {
            name: {
                "sha256": _sha(data),
                "size_bytes": len(data),
            }
            for name, data in sorted(payloads.items())
        },
    }
    _MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    print(json.dumps(build_packet(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
