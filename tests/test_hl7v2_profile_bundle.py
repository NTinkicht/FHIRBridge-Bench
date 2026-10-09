from hashlib import sha256
from pathlib import Path

import pytest

from fhirbridge.hl7v2_profile_bundle import (
    assert_oru_r01_v251_profile,
    assert_single_oru_r01_profile,
    compute_profile_bundle_manifest,
    inspect_profile_identity,
    inspect_profile_messages,
)


def test_profile_bundle_requires_profile_xml(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="PROFILE.xml"):
        compute_profile_bundle_manifest(tmp_path)


def test_profile_bundle_hash_is_deterministic_and_ignores_unknown_files(
    tmp_path: Path,
) -> None:
    (tmp_path / "PROFILE.xml").write_text("<profile/>", encoding="utf-8")
    (tmp_path / "CONSTRAINTS.xml").write_text("<constraints/>", encoding="utf-8")
    (tmp_path / ".DS_Store").write_text("ignored", encoding="utf-8")

    first = compute_profile_bundle_manifest(tmp_path)
    second = compute_profile_bundle_manifest(tmp_path)

    assert first == second
    assert [item.name for item in first.files] == ["PROFILE.xml", "CONSTRAINTS.xml"]
    assert first.files[0].sha256 == sha256(b"<profile/>").hexdigest()
    assert len(first.aggregate_sha256) == 64


def test_profile_bundle_hash_changes_when_scientific_artifact_changes(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "PROFILE.xml"
    profile.write_text("<profile version=\"a\"/>", encoding="utf-8")
    before = compute_profile_bundle_manifest(tmp_path)

    profile.write_text("<profile version=\"b\"/>", encoding="utf-8")
    after = compute_profile_bundle_manifest(tmp_path)

    assert before.aggregate_sha256 != after.aggregate_sha256
    assert before.files[0].sha256 != after.files[0].sha256


def test_optional_igamt_bundle_files_are_included_in_fixed_order(
    tmp_path: Path,
) -> None:
    for name in (
        "PROFILE.xml",
        "SLICINGS.xml",
        "VALUESETS.xml",
        "COCONSTRAINTS.xml",
        "VALUESETBINDINGS.xml",
        "CONSTRAINTS.xml",
    ):
        (tmp_path / name).write_text(f"<{name}/>", encoding="utf-8")

    manifest = compute_profile_bundle_manifest(tmp_path)

    assert [item.name for item in manifest.files] == [
        "PROFILE.xml",
        "CONSTRAINTS.xml",
        "VALUESETS.xml",
        "VALUESETBINDINGS.xml",
        "COCONSTRAINTS.xml",
        "SLICINGS.xml",
    ]
    assert manifest.to_dict()["aggregate_sha256"] == manifest.aggregate_sha256


def test_profile_identity_extracts_v251_oru_r01_attributes(tmp_path: Path) -> None:
    (tmp_path / "PROFILE.xml").write_text(
        (
            '<HL7v2xConformanceProfile HL7Version="2.5.1">'
            '<HL7v2xStaticDef MsgType="ORU" EventType="R01" '
            'MsgStructID="ORU_R01"/>'
            "</HL7v2xConformanceProfile>"
        ),
        encoding="utf-8",
    )

    identity = inspect_profile_identity(tmp_path)

    assert identity.hl7_version == "2.5.1"
    assert identity.message_type == "ORU"
    assert identity.event_type == "R01"
    assert identity.message_structure == "ORU_R01"
    assert_oru_r01_v251_profile(tmp_path)


def test_profile_identity_supports_nist_conformance_profile_message_attributes(
    tmp_path: Path,
) -> None:
    (tmp_path / "PROFILE.xml").write_text(
        (
            '<ConformanceProfile HL7Version="2.5.1">'
            '<Messages>'
            '<Message Type="ACK" Event="R01" StructID="ACK"/>'
            '<Message Description="Laboratory Results Interface" '
            'Type="ORU" Event="R01" StructID="ORU_R01"/>'
            '</Messages>'
            '</ConformanceProfile>'
        ),
        encoding="utf-8",
    )

    identity = inspect_profile_identity(tmp_path)

    assert identity.hl7_version == "2.5.1"
    assert identity.message_type == "ORU"
    assert identity.event_type == "R01"
    assert identity.message_structure == "ORU_R01"
    assert_oru_r01_v251_profile(tmp_path)

def test_single_oru_guard_rejects_ambiguous_multi_variant_profile(
    tmp_path: Path,
) -> None:
    (tmp_path / "PROFILE.xml").write_text(
        (
            '<ConformanceProfile HL7Version="2.5.1">'
            '<Messages>'
            '<Message ID="ORU_R01:LRI_GU" Type="ORU" Event="R01" '
            'StructID="ORU_R01"/>'
            '<Message ID="ORU_R01:LRI_NG" Type="ORU" Event="R01" '
            'StructID="ORU_R01"/>'
            '</Messages>'
            '</ConformanceProfile>'
        ),
        encoding="utf-8",
    )

    messages = inspect_profile_messages(tmp_path)
    assert [message.identifier for message in messages] == [
        "ORU_R01:LRI_GU",
        "ORU_R01:LRI_NG",
    ]
    with pytest.raises(ValueError, match="exactly one ORU\\^R01"):
        assert_single_oru_r01_profile(tmp_path)


def test_single_oru_guard_accepts_one_selected_profile(tmp_path: Path) -> None:
    (tmp_path / "PROFILE.xml").write_text(
        (
            '<ConformanceProfile HL7Version="2.5.1">'
            '<Messages>'
            '<Message ID="ORU_R01:LRI_SELECTED" '
            'Description="Laboratory Results Interface" Type="ORU" '
            'Event="R01" StructID="ORU_R01"/>'
            '</Messages>'
            '</ConformanceProfile>'
        ),
        encoding="utf-8",
    )

    selected = assert_single_oru_r01_profile(tmp_path)

    assert selected.identifier == "ORU_R01:LRI_SELECTED"
    assert selected.description == "Laboratory Results Interface"

def test_profile_identity_rejects_wrong_message_or_version(tmp_path: Path) -> None:
    (tmp_path / "PROFILE.xml").write_text(
        (
            '<HL7v2xConformanceProfile HL7Version="2.3.1">'
            '<HL7v2xStaticDef MsgType="ADT" EventType="A01" '
            'MsgStructID="ADT_A01"/>'
            "</HL7v2xConformanceProfile>"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required HL7 v2.5.1 ORU"):
        assert_oru_r01_v251_profile(tmp_path)


def test_profile_identity_rejects_malformed_xml(tmp_path: Path) -> None:
    (tmp_path / "PROFILE.xml").write_text("<broken>", encoding="utf-8")

    with pytest.raises(ValueError, match="not well-formed XML"):
        inspect_profile_identity(tmp_path)


def test_profile_guard_rejects_oru_when_wrapper_would_select_another_message(
    tmp_path: Path,
) -> None:
    (tmp_path / "PROFILE.xml").write_text(
        (
            '<ConformanceProfile HL7Version="2.5.1">'
            '<Messages>'
            '<Message ID="ACK-FIRST" Type="ACK" Event="R01" StructID="ACK"/>'
            '<Message ID="ORU-SECOND" Type="ORU" Event="R01" StructID="ORU_R01"/>'
            '</Messages>'
            '</ConformanceProfile>'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="first declared message profile"):
        assert_single_oru_r01_profile(tmp_path)
