"""Build a blind independent Edition 5 required-element extraction packet."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

_SCHEMA = Path(
    "qualification/hl7v2/required_element_review/schema/"
    "required_element_extraction.schema.json"
)
_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/"
    "extraction_template.yaml"
)
_OUTPUT_DIR = Path("qualification/hl7v2/required_element_review/generated")
_PACKET = _OUTPUT_DIR / "lri-edition5-required-element-blind-extraction.zip"
_MANIFEST = _OUTPUT_DIR / "lri-edition5-required-element-blind-extraction-manifest.json"

_SOURCE_SHA256 = (
    "375f02fd5453b06ff1c51841e703c943c3132134fca53a122f5ccfed743461b7"
)
_ERRATA_SHA256 = (
    "32eeb375ecb78dd77acb01ed388e30c554688e55a8a4d58df05dd0e7a791700f"
)
_PROFILE_NAME = "LRI_NG_FRU_Profile_V3"
_COMPONENTS = (
    "LRI_Common_Component_V3",
    "LRI_NG_Component_R1",
    "LAB_FRU_Component",
)

_FORBIDDEN_TEXT = (
    "benchmark/lri_required_element_inventory.yaml",
    "renderer a",
    "renderer_a",
    "hl7v251_oru_a.py",
    "current project inventory",
)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _readme() -> str:
    return f"""FHIRBridge-Bench blind Edition 5 required-element extraction

Source artifact
---------------
HL7 Version 2.5.1 Implementation Guide: Laboratory Results Interface (LRI),
Edition 5, US Realm, May 2024 with December 2024 Errata.

Expected implementation-guide PDF SHA-256:
{_SOURCE_SHA256}
Expected December 2024 errata-letter PDF SHA-256:
{_ERRATA_SHA256}

Profile candidate:
{_PROFILE_NAME}

Components:
- {_COMPONENTS[0]}
- {_COMPONENTS[1]}
- {_COMPONENTS[2]}

Purpose
-------
Independently enumerate every applicable group, segment, field, component,
subcomponent, binding and conditional constraint within the bounded ORU^R01
general-laboratory Common+NG+FRU slice. Cover MSH, PID, ORC, OBR, OBX, SPM,
and NTE if included, plus constraints connecting these elements.

This is Path B: bounded PDF-derived qualification work, NOT a claim of
full conformance to a machine-readable Edition 5 IGAMT profile.
An independent reviewer will adjudicate and separately audit completeness.
A matching or schema-valid extraction alone does not establish completeness.

Do not use another extractor's work, project implementation code, converter
output, or project-authored requirement inventories as requirement evidence.

For each locus record:
- element level;
- usage;
- cardinality;
- datatype and maximum length where constrained;
- condition/predicate where applicable;
- value-set/binding reference where applicable;
- source-grounding classification:
  SOURCE_FACT, PROFILE_CONSTANT, ENVELOPE, DERIVED, UNPROJECTABLE, or UNRESOLVED;
- exact source page/table/profile evidence.

UNKNOWN/UNRESOLVED is preferable to guessing. Mark extraction_complete=true
only after you have exhausted the bounded Common + NG + FRU slice.

Important
---------
The implementation-guide PDF and errata letter are NOT embedded here. Use
copies matching both hashes, and record BOTH SHA-256 digests in the
returned extraction's source section. Document exact page/table evidence
(plus errata disposition) for each claim. Do not infer requirements from any
project implementation or historical NIST profile. If an original complete
Edition 5 machine-readable profile is acquired later, it is a separately
qualified sensitivity comparator, not required to start Path B extraction.
Never classify an unresolved requirement as compliant by default.
"""


def _canonical_member(name: str) -> ZipInfo:
    """Fixed ZIP metadata so byte hashes do not depend on build clock/OS."""
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 << 16)
    return info


def build_packet() -> dict[str, object]:
    schema = _SCHEMA.read_bytes()
    template = _TEMPLATE.read_bytes()
    readme = _readme().encode("utf-8")

    payloads = {
        "README.txt": readme,
        "required-element-extraction.schema.json": schema,
        "extraction-template.yaml": template,
    }
    for name, data in payloads.items():
        lowered = data.decode("utf-8", errors="replace").lower()
        for token in _FORBIDDEN_TEXT:
            if token in lowered:
                raise ValueError(f"{name} leaks forbidden project material: {token}")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(_PACKET, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(payloads):
            archive.writestr(_canonical_member(name), payloads[name])

    manifest = {
        "packet_id": "FHIRBRIDGE-LRI-E5-BLIND-EXTRACTION-001",
        "profile_name": _PROFILE_NAME,
        "components": list(_COMPONENTS),
        "source_pdf_sha256": _SOURCE_SHA256,
        "errata_pdf_sha256": _ERRATA_SHA256,
        "development_path": "bounded_independent_reconstruction",
        "full_edition5_profile_conformance_claim": False,
        "includes_provisional_project_inventory": False,
        "packet_path": str(_PACKET),
        "packet_sha256": _sha256_bytes(_PACKET.read_bytes()),
        "contents": {
            name: {
                "sha256": _sha256_bytes(data),
                "size_bytes": len(data),
            }
            for name, data in sorted(payloads.items())
        },
        "project_inventory_included": False,
        "renderer_material_included": False,
        "source_pdf_embedded": False,
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
