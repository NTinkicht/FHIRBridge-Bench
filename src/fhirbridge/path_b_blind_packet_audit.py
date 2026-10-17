"""Fail-closed byte audit of a neutral, *unassigned* Path B reviewer ZIP.

Only detects packaging/manifest drift against separately supplied trusted
source payload bytes. It cannot authenticate a reviewer or PDF license, and
does not authorize external distribution, standards qualification or G1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from stat import S_IFLNK
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from .lri_source_identity import pinned_publication_hashes

_ALLOWED_NAMES = frozenset(
    {"README.txt", "required-element-extraction.schema.json", "extraction-template.yaml"}
)
_MANIFEST_KEYS = frozenset(
    {
        "packet_id", "profile_name", "components", "source_pdf_sha256",
        "errata_pdf_sha256", "development_path",
        "full_edition5_profile_conformance_claim",
        "includes_provisional_project_inventory", "packet_path",
        "packet_sha256", "contents", "project_inventory_included",
        "renderer_material_included", "source_pdf_embedded",
    }
)
_SOURCE_COMPONENTS = frozenset(
    {"LRI_Common_Component_V3", "LRI_NG_Component_R1", "LAB_FRU_Component"}
)
_FORBIDDEN_SPANS = (
    b"benchmark/lri_required_element_inventory.yaml",
    b"src/fhirbridge/renderers/",
    b"hl7v251_oru_a.py",
    b"renderer_a",
    b"current project inventory",
    b"contracts/fhir_to_v2/",
)
_MAX_ENTRY_BYTES = 2 * 1024 * 1024
_MAX_PACKET_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class PacketIntegrityAudit:
    packet_sha256: str
    checked_entries: tuple[str, ...]
    packet_byte_count: int

    @property
    def status(self) -> str:
        return "BLIND_PACKET_BYTES_MATCHED_ONLY"

    @property
    def independent_extraction_received(self) -> bool:
        return False

    @property
    def official_source_pdfs_verified_or_licensed(self) -> bool:
        return False

    @property
    def G1_qualified(self) -> bool:
        return False

    @property
    def external_distribution_authorized(self) -> bool:
        return False


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def audit_blind_packet_bytes(
    *,
    packet_bytes: bytes,
    manifest_bytes: bytes,
    expected_payloads: dict[str, bytes],
    expected_packet_path: str,
) -> PacketIntegrityAudit:
    """Compare a generated ZIP and manifest to three trusted input payloads.

    Caller must obtain the trusted payloads independently from the generated
    ZIP. This remains a mechanical audit, not a cryptographic signature.
    """
    if (
        not isinstance(packet_bytes, bytes)
        or not packet_bytes
        or len(packet_bytes) > _MAX_PACKET_BYTES
        or not isinstance(manifest_bytes, bytes)
        or len(manifest_bytes) > _MAX_ENTRY_BYTES
    ):
        raise ValueError("packet or manifest bytes invalid or oversized")
    if (
        not isinstance(expected_payloads, dict)
        or set(expected_payloads) != _ALLOWED_NAMES
        or any(
            not isinstance(value, bytes) or len(value) > _MAX_ENTRY_BYTES
            for value in expected_payloads.values()
        )
    ):
        raise ValueError("trusted reviewer input allowlist is not exact")
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate manifest JSON key: {key}")
            result[key] = value
        return result

    try:
        manifest = json.loads(
            manifest_bytes.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS:
        raise ValueError("unexpected manifest keys or missing safety metadata")

    pins = pinned_publication_hashes()
    if (
        manifest["packet_id"] != "FHIRBRIDGE-LRI-E5-BLIND-EXTRACTION-001"
        or manifest["profile_name"] != "LRI_NG_FRU_Profile_V3"
        or not isinstance(manifest["components"], list)
        or len(manifest["components"]) != 3
        or set(manifest["components"]) != _SOURCE_COMPONENTS
        or manifest["source_pdf_sha256"] != pins["implementation_guide"]
        or manifest["errata_pdf_sha256"] != pins["errata_letter"]
        or manifest["development_path"] != "bounded_independent_reconstruction"
        or manifest["packet_path"] != expected_packet_path
        or manifest["packet_sha256"] != _sha(packet_bytes)
    ):
        raise ValueError("manifest source, bounded scope or full ZIP SHA-256 mismatch")
    for key in (
        "full_edition5_profile_conformance_claim",
        "includes_provisional_project_inventory",
        "project_inventory_included",
        "renderer_material_included",
        "source_pdf_embedded",
    ):
        if manifest[key] is not False:
            raise ValueError(f"manifest must not make unsafe claim: {key}")

    contents = manifest["contents"]
    if not isinstance(contents, dict) or set(contents) != _ALLOWED_NAMES:
        raise ValueError("manifest contains unknown or missing ZIP members")

    try:
        with ZipFile(BytesIO(packet_bytes), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(_ALLOWED_NAMES) or set(names) != _ALLOWED_NAMES:
                raise ValueError("ZIP members missing, duplicated or not allowlisted")
            for info in infos:
                name = info.filename
                if (
                    info.is_dir()
                    or info.flag_bits & 1
                    or info.compress_type != ZIP_DEFLATED
                    or (info.external_attr >> 16) & 0o170000 == S_IFLNK
                    or info.file_size > _MAX_ENTRY_BYTES
                ):
                    raise ValueError(f"unsafe ZIP metadata: {name}")
                actual = archive.read(info)
                source = expected_payloads[name]
                if actual != source:
                    raise ValueError(f"ZIP member does not match trusted source bytes: {name}")
                low = actual.lower()
                if any(token in low for token in _FORBIDDEN_SPANS):
                    raise ValueError(f"ZIP member contains restricted project material: {name}")
                entry = contents[name]
                if (
                    not isinstance(entry, dict)
                    or set(entry) != {"sha256", "size_bytes"}
                    or entry["sha256"] != _sha(actual)
                    or type(entry["size_bytes"]) is not int
                    or entry["size_bytes"] != len(actual)
                ):
                    raise ValueError(f"member manifest digest/size mismatch: {name}")
    except (BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("ZIP malformed or unreadable") from exc

    # The neutral builder writes an exact deterministic archive with only
    # three entries. A ZIP parser can ignore hidden data before/after that
    # envelope, so checking only members and the manifest is insufficient.
    # Rebuilding precisely also fails closed on trailing ZIP comments.
    reconstructed = BytesIO()
    with ZipFile(reconstructed, "w", compression=ZIP_DEFLATED) as canonical:
        for name in sorted(_ALLOWED_NAMES):
            # Match the *fixed public packet format*, not a new ZIP whose
            # incidental timestamp is based on the auditor's wall clock.
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            canonical.writestr(entry, expected_payloads[name])
    if reconstructed.getvalue() != packet_bytes:
        raise ValueError("ZIP envelope or serialization is not canonical")

    return PacketIntegrityAudit(
        packet_sha256=_sha(packet_bytes),
        checked_entries=tuple(sorted(_ALLOWED_NAMES)),
        packet_byte_count=len(packet_bytes),
    )


def audit_blind_packet_files(
    *,
    packet: Path,
    manifest: Path,
    expected_payloads: dict[str, bytes],
) -> PacketIntegrityAudit:
    """Read a public packet for an integrity check, without opening source PDFs."""
    return audit_blind_packet_bytes(
        packet_bytes=packet.read_bytes(),
        manifest_bytes=manifest.read_bytes(),
        expected_payloads=expected_payloads,
        expected_packet_path=str(packet),
    )
