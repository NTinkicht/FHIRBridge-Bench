from pathlib import Path
from zipfile import ZipFile

import pytest

from fhirbridge.hl7v2_profile_archive import inspect_profile_archive


def _profile_xml() -> str:
    return (
        '<ConformanceProfile HL7Version="2.5.1">'
        "<Messages>"
        '<Message ID="LRI_TEST" Description="Laboratory Results Interface" '
        'Type="ORU" Event="R01" StructID="ORU_R01"/>'
        "</Messages>"
        "</ConformanceProfile>"
    )


def test_profile_archive_inspection_accepts_nested_single_bundle(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "profile.zip"
    with ZipFile(archive, "w") as output:
        output.writestr("bundle/PROFILE.xml", _profile_xml())
        output.writestr("bundle/CONSTRAINTS.xml", "<constraints/>")
        output.writestr("bundle/notes.txt", "preserved")
        output.writestr("bundle/resources/custom.xml", "<custom/>")
        output.writestr("other/CONSTRAINTS.xml", "<not-selected/>")

    inspection = inspect_profile_archive(archive)

    assert len(inspection.archive_sha256) == 64
    assert inspection.source_directory == "bundle"
    assert inspection.identity.hl7_version == "2.5.1"
    assert inspection.selected_message.identifier == "LRI_TEST"
    assert [item.name for item in inspection.manifest.files] == [
        "PROFILE.xml",
        "CONSTRAINTS.xml",
        "notes.txt",
        "resources/custom.xml",
    ]


def test_profile_archive_rejects_multiple_profile_xml_files(tmp_path: Path) -> None:
    archive = tmp_path / "profile.zip"
    with ZipFile(archive, "w") as output:
        output.writestr("a/PROFILE.xml", _profile_xml())
        output.writestr("b/PROFILE.xml", _profile_xml())

    with pytest.raises(ValueError, match="exactly one PROFILE.xml"):
        inspect_profile_archive(archive)


def test_profile_archive_rejects_multiple_oru_profiles(tmp_path: Path) -> None:
    archive = tmp_path / "profile.zip"
    profile = (
        '<ConformanceProfile HL7Version="2.5.1"><Messages>'
        '<Message ID="A" Type="ORU" Event="R01" StructID="ORU_R01"/>'
        '<Message ID="B" Type="ORU" Event="R01" StructID="ORU_R01"/>'
        "</Messages></ConformanceProfile>"
    )
    with ZipFile(archive, "w") as output:
        output.writestr("PROFILE.xml", profile)

    with pytest.raises(ValueError, match="exactly one ORU"):
        inspect_profile_archive(archive)


def test_profile_archive_ignores_path_traversal_outside_selected_subtree(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "profile.zip"
    with ZipFile(archive, "w") as output:
        output.writestr("bundle/PROFILE.xml", _profile_xml())
        output.writestr("../PROFILE.xml.bak", "not scientific input")
        output.writestr("bundle/../../evil.txt", "must not be extracted")

    inspection = inspect_profile_archive(archive)

    assert [item.name for item in inspection.manifest.files] == ["PROFILE.xml"]


def test_archive_inspection_carries_reference_inventory(tmp_path: Path) -> None:
    archive = tmp_path / "profile-signals.zip"
    profile = (
        '<ConformanceProfile HL7Version="2.5.1"><Messages>'
        '<Message ID="LRI_NG_FRU_Profile_V3" Type="ORU" Event="R01" '
        'StructID="ORU_R01" OID="2.16.840.1.113883.9.195.3.25"/>'
        '</Messages>'
        '<Component OID="2.16.840.1.113883.9.195.3.22"/>'
        '<Component OID="2.16.840.1.113883.9.13"/>'
        '<Component OID="2.16.840.1.113883.9.83"/>'
        '</ConformanceProfile>'
    )
    with ZipFile(archive, "w") as output:
        output.writestr("bundle/PROFILE.xml", profile)

    inspection = inspect_profile_archive(archive)

    assert inspection.target_reference_signals[
        "selected_profile_name_observed"
    ] is True
    assert inspection.target_reference_signals[
        "all_required_component_oid_signals_observed"
    ] is True
    assert any(
        item.value == "2.16.840.1.113883.9.195.3.25"
        for item in inspection.reference_inventory.oids
    )
