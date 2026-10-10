"""Build an external review packet for status/specimen mapping candidates."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

_STATUS = Path("benchmark/status_mapping_candidates.yaml")
_SPECIMEN = Path("benchmark/specimen_binding_candidates.yaml")
_SCHEMA = Path("contracts/review/semantic_mapping_review_response.schema.json")
_OUTPUT_DIR = Path("contracts/review/generated")
_ASSIGNMENT = _OUTPUT_DIR / "semantic-mapping-review-assignment.json"
_PACKET = _OUTPUT_DIR / "semantic-mapping-review-packet.zip"
_MANIFEST = _OUTPUT_DIR / "semantic-mapping-review-packet-manifest.json"


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def _status_items(document: dict) -> list[dict]:
    sources = document["sources"]
    items: list[dict] = []
    for key, target_field, evidence_key in (
        ("diagnostic_report_to_obr25", "OBR-25", "v2_to_fhir_obr25"),
        ("observation_to_obx11", "OBX-11", "v2_to_fhir_obx11"),
    ):
        section = document[key]
        mapping = section["safe_unique_inverse"]
        for source_status, target_code in sorted(mapping.items()):
            items.append(
                {
                    "candidate_id": (
                        f"{key.upper()}::{source_status}::{target_code}"
                    ),
                    "candidate_type": "status_reverse_mapping",
                    "source_semantic": source_status,
                    "target_locus": target_field,
                    "target_code": target_code,
                    "target_display": None,
                    "evidence": [
                        sources[evidence_key]["url"],
                        sources[
                            "fhir_r4_diagnostic_report_status"
                            if key == "diagnostic_report_to_obr25"
                            else "fhir_r4_observation_status"
                        ]["url"],
                    ],
                    "candidate_derivation": "unique_inverse_of_published_v2_to_FHIR_map",
                    "requires_exact_profile_binding_confirmation": True,
                }
            )
    return items


def _specimen_items(document: dict) -> list[dict]:
    candidates = document["candidate_projection_after_binding_review"]
    terminology = document["authoritative_generic_terminology"]
    return [
        {
            "candidate_id": "SPECIMEN_TYPE::serum::SER",
            "candidate_type": "specimen_code_mapping",
            "source_semantic": "serum",
            "target_locus": "SPM-4",
            "target_code": candidates["serum_to_SPM_4"]["candidate_code"],
            "target_display": candidates["serum_to_SPM_4"]["candidate_display"],
            "evidence": [
                terminology["specimen_type"]["code_system_url"],
                terminology["specimen_type"]["value_set_url"],
            ],
            "candidate_derivation": "generic_HL7_v2_terminology_candidate",
            "requires_exact_profile_binding_confirmation": True,
        },
        {
            "candidate_id": "COLLECTION_METHOD::venipuncture::VENIP",
            "candidate_type": "specimen_code_mapping",
            "source_semantic": "venipuncture",
            "target_locus": "SPM-7",
            "target_code": candidates["venipuncture_to_SPM_7"]["candidate_code"],
            "target_display": candidates["venipuncture_to_SPM_7"]["candidate_display"],
            "evidence": [
                terminology["collection_method"]["code_system_url"],
                terminology["collection_method"]["value_set_url"],
            ],
            "candidate_derivation": "generic_HL7_v2_terminology_candidate",
            "requires_exact_profile_binding_confirmation": True,
        },
    ]


def _readme(item_count: int) -> str:
    return f"""FHIRBridge-Bench independent semantic mapping candidate review

Items: {item_count}

Purpose
-------
Independently evaluate candidate reverse status mappings and specimen terminology
mappings for the bounded FHIR R4 / US Core 9.0.0 to HL7 v2.5.1 LRI Edition 5
laboratory study.

These are candidates, not ground truth. The status candidates are unique
inverses of published v2-to-FHIR concept-map entries. The specimen candidates
exist in generic HL7 v2 terminology. Neither fact alone proves that the reverse
mapping is correct and applicable under the selected Edition 5 profile.

For each item choose:
- ACCEPT
- REJECT
- INDETERMINATE

Also state whether profile applicability is CONFIRMED, NOT_APPLICABLE, or
REQUIRES_EXACT_PROFILE.

When the exact Edition 5 machine profile or exact applicable laboratory
value-set companion artifact is needed to decide an item, use INDETERMINATE /
REQUIRES_EXACT_PROFILE rather than guessing.

Review independently. Do not use Renderer A/Renderer B outputs or another
reviewer's decisions as correctness evidence.
"""


def build_packet() -> dict[str, object]:
    status = _load(_STATUS)
    specimen = _load(_SPECIMEN)
    items = _status_items(status) + _specimen_items(specimen)
    candidate_ids = [item["candidate_id"] for item in items]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("duplicate semantic mapping candidate IDs")

    assignment = {
        "assignment_id": "FHIRBRIDGE-SEMANTIC-MAPPING-REVIEW-001",
        "schema_version": "0.1.0",
        "review_stage": "independent_candidate_review",
        "target_profile_candidate": "LRI_NG_FRU_Profile_V3",
        "edition": "5",
        "errata": "2024DEC",
        "item_count": len(items),
        "items": items,
        "independence": {
            "other_reviewer_decisions_permitted": False,
            "renderer_outputs_permitted_as_correctness_evidence": False,
            "indeterminate_preferred_to_profile_guessing": True,
        },
        "response_schema": str(_SCHEMA),
    }
    assignment_bytes = (
        json.dumps(assignment, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    schema_bytes = _SCHEMA.read_bytes()
    readme_bytes = _readme(len(items)).encode("utf-8")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _ASSIGNMENT.write_bytes(assignment_bytes)
    payloads = {
        "assignment.json": assignment_bytes,
        "response-schema.json": schema_bytes,
        "README.txt": readme_bytes,
    }
    with ZipFile(_PACKET, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(payloads):
            archive.writestr(name, payloads[name])

    manifest = {
        "packet_id": "FHIRBRIDGE-SEMANTIC-MAPPING-REVIEW-PACKET-001",
        "assignment_sha256": _sha256_bytes(assignment_bytes),
        "packet_sha256": _sha256_bytes(_PACKET.read_bytes()),
        "item_count": len(items),
        "packet_path": str(_PACKET),
        "contents": {
            name: {
                "sha256": _sha256_bytes(data),
                "size_bytes": len(data),
            }
            for name, data in sorted(payloads.items())
        },
        "reviewer_decisions_included": False,
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
