"""Build a self-contained blind Stage-1 external contract-review packet."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import fhirbridge.schema_validation
from fhirbridge.contract_review_assignment import build_contract_review_assignment

_CONTRACT = Path("contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml")
_CANDIDATES = Path("contracts/review/relationship_candidates_v0.2.yaml")
_SCHEMA = Path("contracts/review/contract_review_blind_response.schema.json")
_OUTPUT_DIR = Path("contracts/review/generated")
_PACKET = _OUTPUT_DIR / "contract-review-stage1-blind-v0.3.zip"
_MANIFEST = _OUTPUT_DIR / "contract-review-stage1-blind-v0.3-manifest.json"

_FORBIDDEN_KEYS = frozenset(
    {
        "target_paths",
        "target_semantics",
        "proposed_projectability",
        "proposed_allowed_operations",
        "proposed_equivalence",
        "proposed_failure_types",
        "proposed_severity",
        "status",
    }
)
_FORBIDDEN_TEXT = (
    "renderer a",
    "renderer_a",
    "fhir_r4_a.py",
    "hl7v251_oru_a.py",
    "study team's proposed target",
)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _scan_forbidden(value: object, *, path: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_KEYS:
                problems.append(f"{path}.{key}: proposal field leaked")
            problems.extend(_scan_forbidden(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            problems.extend(_scan_forbidden(child, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for token in _FORBIDDEN_TEXT:
            if token in lowered:
                problems.append(f"{path}: forbidden text leaked: {token}")
    return problems


def _readme(assignment: dict) -> str:
    return f"""FHIRBridge-Bench blind Stage-1 projectability review

Assignment ID: {assignment["assignment_id"]}
Contract under review: {assignment["contract"]["id"]} v{assignment["contract"]["version"]}
Review stage: blind
Items: {assignment["review_item_count"]}

Purpose
-------
Independently classify the projectability of each supplied canonical source
fact/relation for the named FHIR R4 / US Core 9.0.0 to HL7 v2.5.1 LRI Edition 5
laboratory scope.

This Stage-1 packet intentionally withholds the study team's proposed target
locus, projectability label, transformation operations, equivalence rule,
failure class, severity, and renderer behavior.

Allowed evidence
----------------
Use the cited standards/profile material and your own standards expertise.
Do not use model outputs, verifier decisions, converter outputs, or another
reviewer's labels as correctness evidence.

Required response
-----------------
Complete one response conforming to response-schema.json. For every rule choose
one of:
MUST_PRESERVE, MAY_TRANSFORM, MAY_LOSE, MUST_NOT_INFER, or INDETERMINATE.

INDETERMINATE is the correct response when the available Edition 5 evidence is
insufficient, including where the exact machine-readable profile is needed to
resolve a question.

Independence
------------
Do not discuss your initial classifications with the other Stage-1 reviewer.
Disclose conflicts, prior project involvement, and any LRI authoring
involvement. Your original Stage-1 response will be retained and hashed before
any proposal-aware Stage-2 material is revealed.
"""


def build_packet() -> dict:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    candidates = fhirbridge.schema_validation.load_yaml(_CANDIDATES)
    assignment = build_contract_review_assignment(
        contract,
        candidates,
        stage="blind",
    )
    if assignment.get("proposal_disclosure") != (
        "withheld_for_independent_initial_classification"
    ):
        raise ValueError("blind assignment proposal-disclosure state is invalid")

    problems = _scan_forbidden(assignment)
    if problems:
        raise ValueError(
            "blind review assignment leaked proposal/renderer information: "
            + "; ".join(problems)
        )

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    readme = _readme(assignment)

    payloads = {
        "assignment.json": (
            json.dumps(assignment, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "response-schema.json": (
            json.dumps(schema, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "README.txt": readme.encode("utf-8"),
    }
    for name, data in payloads.items():
        lowered = data.decode("utf-8", errors="replace").lower()
        if name != "response-schema.json":
            for token in _FORBIDDEN_TEXT:
                if token in lowered:
                    raise ValueError(f"{name} contains forbidden text: {token}")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(_PACKET, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(payloads):
            archive.writestr(name, payloads[name])

    packet_bytes = _PACKET.read_bytes()
    manifest = {
        "packet_id": "FHIRBRIDGE-CONTRACT-REVIEW-STAGE1-BLIND-001",
        "contract_version": assignment["contract"]["version"],
        "assignment_sha256": assignment["assignment_sha256"],
        "packet_sha256": _sha256_bytes(packet_bytes),
        "packet_path": str(_PACKET),
        "contents": {
            name: {
                "sha256": _sha256_bytes(data),
                "size_bytes": len(data),
            }
            for name, data in sorted(payloads.items())
        },
        "proposal_material_included": False,
        "renderer_outputs_included": False,
        "review_stage": "blind",
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
