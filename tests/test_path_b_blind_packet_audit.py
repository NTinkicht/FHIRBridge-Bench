"""Blind reviewer ZIP release audit is structural, never expert signoff."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from io import BytesIO
from stat import S_IFLNK
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import json
import pytest

from fhirbridge.path_b_blind_packet_audit import audit_blind_packet_bytes
from qualification.hl7v2.required_element_review.build_blind_packet import (
    _SCHEMA, _TEMPLATE, _readme,
)

_PACKET_PATH = "qualification/hl7v2/required_element_review/generated/test-blind.zip"
_GUIDE = "375f02fd5453b06ff1c51841e703c943c3132134fca53a122f5ccfed743461b7"
_ERRATA = "32eeb375ecb78dd77acb01ed388e30c554688e55a8a4d58df05dd0e7a791700f"


def _inputs() -> dict[str, bytes]:
    return {
        "README.txt": _readme().encode("utf-8"),
        "required-element-extraction.schema.json": _SCHEMA.read_bytes(),
        "extraction-template.yaml": _TEMPLATE.read_bytes(),
    }


def _zip(entries: list[tuple[str, bytes]], *, symlink: bool = False) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries:
            info = ZipInfo(name)
            info.compress_type = ZIP_DEFLATED
            if symlink and name == "README.txt":
                info.create_system = 3
                info.external_attr = (S_IFLNK | 0o777) << 16
            archive.writestr(info, content)
    return out.getvalue()


def _fixture() -> tuple[bytes, dict, dict[str, bytes]]:
    payloads = _inputs()
    packet = _zip(sorted(payloads.items()))
    manifest = {
        "packet_id": "FHIRBRIDGE-LRI-E5-BLIND-EXTRACTION-001",
        "profile_name": "LRI_NG_FRU_Profile_V3",
        "components": [
            "LRI_Common_Component_V3", "LRI_NG_Component_R1", "LAB_FRU_Component",
        ],
        "source_pdf_sha256": _GUIDE,
        "errata_pdf_sha256": _ERRATA,
        "development_path": "bounded_independent_reconstruction",
        "full_edition5_profile_conformance_claim": False,
        "includes_provisional_project_inventory": False,
        "packet_path": _PACKET_PATH,
        "packet_sha256": sha256(packet).hexdigest(),
        "contents": {
            name: {"sha256": sha256(value).hexdigest(), "size_bytes": len(value)}
            for name, value in payloads.items()
        },
        "project_inventory_included": False,
        "renderer_material_included": False,
        "source_pdf_embedded": False,
    }
    return packet, manifest, payloads


def _audit(packet: bytes, manifest: dict, trusted: dict[str, bytes]):
    return audit_blind_packet_bytes(
        packet_bytes=packet,
        manifest_bytes=json.dumps(manifest).encode("utf-8"),
        expected_payloads=trusted,
        expected_packet_path=_PACKET_PATH,
    )


def test_clean_packet_only_establishes_byte_integrity() -> None:
    packet, manifest, trusted = _fixture()
    report = _audit(packet, manifest, trusted)
    assert report.checked_entries == tuple(sorted(trusted))
    assert report.packet_sha256 == sha256(packet).hexdigest()
    assert report.status == "BLIND_PACKET_BYTES_MATCHED_ONLY"
    assert report.independent_extraction_received is False
    assert report.official_source_pdfs_verified_or_licensed is False
    assert report.G1_qualified is False
    assert report.external_distribution_authorized is False


@pytest.mark.parametrize("claim", [
    "full_edition5_profile_conformance_claim",
    "includes_provisional_project_inventory",
    "project_inventory_included",
    "renderer_material_included",
    "source_pdf_embedded",
])
def test_manifest_cannot_override_an_unsafe_claim(claim: str) -> None:
    packet, manifest, trusted = _fixture()
    manifest[claim] = True
    with pytest.raises(ValueError, match="unsafe claim"):
        _audit(packet, manifest, trusted)


@pytest.mark.parametrize("field", [
    "source_pdf_sha256", "errata_pdf_sha256", "profile_name",
    "development_path", "packet_path", "packet_sha256",
])
def test_normative_source_and_zip_identity_are_pinned(field: str) -> None:
    packet, manifest, trusted = _fixture()
    manifest[field] = "WRONG"
    with pytest.raises(ValueError, match="manifest source"):
        _audit(packet, manifest, trusted)


def test_manifest_cannot_add_g1_authorization() -> None:
    packet, manifest, trusted = _fixture()
    manifest["G1_qualified"] = True
    with pytest.raises(ValueError, match="unexpected manifest keys"):
        _audit(packet, manifest, trusted)


def test_zip_member_bytes_replaced_even_if_manifest_hashes_repaired() -> None:
    packet, manifest, trusted = _fixture()
    entries = list(trusted.items())
    changed = [(n, b"compromised" if n == "README.txt" else v) for n, v in entries]
    packet = _zip(changed)
    manifest["packet_sha256"] = sha256(packet).hexdigest()
    manifest["contents"]["README.txt"] = {
        "sha256": sha256(b"compromised").hexdigest(),
        "size_bytes": len(b"compromised"),
    }
    with pytest.raises(ValueError, match="trusted source bytes"):
        _audit(packet, manifest, trusted)


def test_unexpected_zip_member_is_refused_even_with_updated_digest() -> None:
    packet, manifest, trusted = _fixture()
    packet = _zip(list(trusted.items()) + [("private/clinical.csv", b"PHI")])
    manifest["packet_sha256"] = sha256(packet).hexdigest()
    with pytest.raises(ValueError, match="members missing, duplicated"):
        _audit(packet, manifest, trusted)


def test_duplicate_zip_name_is_rejected_not_silently_overwritten() -> None:
    packet, manifest, trusted = _fixture()
    packet = _zip(list(trusted.items()) + [("README.txt", b"evil")])
    manifest["packet_sha256"] = sha256(packet).hexdigest()
    with pytest.raises(ValueError, match="members missing, duplicated"):
        _audit(packet, manifest, trusted)


def test_malicious_symlink_entry_cannot_be_distributed() -> None:
    packet, manifest, trusted = _fixture()
    packet = _zip(list(trusted.items()), symlink=True)
    manifest["packet_sha256"] = sha256(packet).hexdigest()
    with pytest.raises(ValueError, match="unsafe ZIP metadata"):
        _audit(packet, manifest, trusted)


def test_corrupted_zip_fails_even_with_matching_manifest_digest() -> None:
    _, manifest, trusted = _fixture()
    packet = b"NOT-A-ZIP"
    manifest["packet_sha256"] = sha256(packet).hexdigest()
    with pytest.raises(ValueError, match="ZIP malformed"):
        _audit(packet, manifest, trusted)


def test_manifest_entry_digest_and_size_are_verified() -> None:
    packet, manifest, trusted = _fixture()
    manifest["contents"]["README.txt"]["size_bytes"] = 1
    with pytest.raises(ValueError, match="member manifest digest/size"):
        _audit(packet, manifest, trusted)


def test_disallowed_trusted_input_set_fails_closed() -> None:
    packet, manifest, trusted = _fixture()
    trusted["other-private-file"] = b"SECRET"
    with pytest.raises(ValueError, match="allowlist is not exact"):
        _audit(packet, manifest, trusted)


def test_leaky_reference_payload_fails_even_if_zip_and_manifest_agree() -> None:
    packet, manifest, trusted = _fixture()
    leaked = b"benchmark/lri_required_element_inventory.yaml"
    trusted["README.txt"] += leaked
    packet = _zip(list(trusted.items()))
    manifest["packet_sha256"] = sha256(packet).hexdigest()
    manifest["contents"]["README.txt"] = {
        "sha256": sha256(trusted["README.txt"]).hexdigest(),
        "size_bytes": len(trusted["README.txt"]),
    }
    with pytest.raises(ValueError, match="restricted project material"):
        _audit(packet, manifest, trusted)


@pytest.mark.parametrize("attribute", [
    "G1_qualified", "external_distribution_authorized",
    "independent_extraction_received",
    "official_source_pdfs_verified_or_licensed",
])
def test_report_cannot_mint_authorization(attribute: str) -> None:
    packet, manifest, trusted = _fixture()
    report = _audit(packet, manifest, trusted)
    with pytest.raises(FrozenInstanceError):
        setattr(report, attribute, True)
    with pytest.raises(TypeError):
        replace(report, **{attribute: True})
