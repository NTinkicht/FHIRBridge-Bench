"""Build a leakage-checked blind severity-calibration packet."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

_ANCHORS = Path("expert_validation/severity_anchor_set.yaml")
_POLICY = Path("benchmark/severity_policy_candidate.yaml")
_SCHEMA = Path("expert_validation/schema/severity_blind_response.schema.json")
_OUTPUT_DIR = Path("expert_validation/generated")
_PACKET = _OUTPUT_DIR / "severity-calibration-stage1-blind.zip"
_MANIFEST = _OUTPUT_DIR / "severity-calibration-stage1-blind-manifest.json"

_FORBIDDEN_TEXT = (
    "expected_boundary_role_internal",
    "primary_endpoint_major_candidate",
    "major_threshold",
    "study_team_preferred_rating",
)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def _readme(anchor_count: int) -> str:
    return f"""FHIRBridge-Bench blind semantic-severity calibration

Anchors: {anchor_count}

Purpose
-------
Independently rate each synthetic transformation difference under the supplied
S0-S3 severity definitions.

Use one of:
S0, S1, S2, S3, or INDETERMINATE.

The anchor-design boundary roles are deliberately hidden. The study's candidate
primary-endpoint threshold is also hidden. Do not discuss your initial ratings
with the other reviewer. Original responses will be retained and hashed before
adjudication or threshold selection.

These are synthetic calibration vignettes, not sealed benchmark cases. Do not
use converter outputs, verifier outputs, or another reviewer's ratings as
correctness evidence.
"""


def build_packet() -> dict[str, object]:
    anchor_doc = _load_yaml(_ANCHORS)
    policy_doc = _load_yaml(_POLICY)
    anchors = anchor_doc.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("severity anchor set is empty")

    visible_anchors: list[dict[str, object]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ValueError("severity anchor is malformed")
        visible = anchor.get("reviewer_visible")
        if not isinstance(visible, dict):
            raise ValueError("severity anchor reviewer_visible block is missing")
        visible_anchors.append(
            {
                "anchor_id": anchor["anchor_id"],
                "title": visible["title"],
                "vignette": visible["vignette"],
                "review_question": visible["review_question"],
            }
        )

    levels = policy_doc.get("levels")
    if not isinstance(levels, dict):
        raise ValueError("severity level definitions are missing")
    visible_levels = {
        key: {
            "label": value["label"],
            "definition": value["definition"],
        }
        for key, value in levels.items()
    }

    assignment = {
        "assignment_id": "FHIRBRIDGE-SEVERITY-BLIND-001",
        "schema_version": "0.1.0",
        "review_stage": "blind_independent_initial_rating",
        "severity_levels": visible_levels,
        "anchors": visible_anchors,
        "response_schema": str(_SCHEMA),
        "proposal_disclosure": "withheld_until_initial_ratings_locked",
    }

    assignment_bytes = (
        json.dumps(assignment, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    schema_bytes = _SCHEMA.read_bytes()
    readme_bytes = _readme(len(visible_anchors)).encode("utf-8")

    for name, data in {
        "assignment.json": assignment_bytes,
        "README.txt": readme_bytes,
    }.items():
        lowered = data.decode("utf-8", errors="replace").lower()
        for token in _FORBIDDEN_TEXT:
            if token.lower() in lowered:
                raise ValueError(f"{name} leaks forbidden calibration material: {token}")

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
        "packet_id": "FHIRBRIDGE-SEVERITY-STAGE1-BLIND-PACKET-001",
        "review_stage": "blind",
        "anchor_count": len(visible_anchors),
        "packet_path": str(_PACKET),
        "packet_sha256": _sha256_bytes(_PACKET.read_bytes()),
        "assignment_sha256": _sha256_bytes(assignment_bytes),
        "contents": {
            name: {
                "sha256": _sha256_bytes(data),
                "size_bytes": len(data),
            }
            for name, data in sorted(payloads.items())
        },
        "boundary_role_metadata_included": False,
        "major_threshold_candidate_included": False,
        "sealed_case_content_included": False,
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
