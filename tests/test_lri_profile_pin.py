from pathlib import Path
from zipfile import ZipFile

import pytest

from fhirbridge.hl7v2_profile_archive import inspect_profile_archive
from fhirbridge.lri_profile_pin import (
    LriAcquisitionMetadata,
    build_lri_profile_pin_candidate,
)


def _archive(path: Path) -> None:
    profile = (
        '<ConformanceProfile HL7Version="2.5.1">'
        '<Messages>'
        '<Message ID="ORU-R01-ONLY" Description="Laboratory Results Interface" '
        'Type="ORU" Event="R01" StructID="ORU_R01"/>'
        '</Messages>'
        '</ConformanceProfile>'
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("bundle/PROFILE.xml", profile)
        archive.writestr("bundle/CONSTRAINTS.xml", "<constraints/>")


def test_profile_pin_candidate_copies_only_machine_verifiable_fields(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "lri.zip"
    _archive(archive)
    inspection = inspect_profile_archive(archive)
    acquisition = LriAcquisitionMetadata(
        source_url_or_record="record://hl7-lri-ed5-export",
        igamt_export_identifier="IGAMT-EXPORT-123",
        acquired_at="2026-10-10T00:00:00+04:00",
        acquired_by_role_id="reviewer-A",
        redistribution_status="metadata_only",
    )

    record = build_lri_profile_pin_candidate(inspection, acquisition)

    assert record["acquisition"]["igamt_export_identifier"] == "IGAMT-EXPORT-123"
    assert len(record["bundle"]["archive_sha256"]) == 64
    assert len(record["bundle"]["aggregate_sha256"]) == 64
    assert len(record["bundle"]["profile_xml_sha256"]) == 64
    assert record["identity_verification"]["profile_xml_hl7_version"] == "2.5.1"
    assert record["identity_verification"]["profile_xml_message_type"] == "ORU"
    assert record["identity_verification"]["profile_xml_event_type"] == "R01"
    assert (
        record["identity_verification"]["profile_xml_message_structure"]
        == "ORU_R01"
    )
    assert record["identity_verification"]["profile_identity_guard_passed"] is True

    # These claims require human/provenance evidence beyond archive structure.
    assert record["identity_verification"]["edition_5_evidence_checked"] is False
    assert (
        record["identity_verification"]["errata_2024dec_evidence_checked"]
        is False
    )
    assert (
        record["identity_verification"]["independent_profile_provenance_reviewed"]
        is False
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "source_url_or_record",
        "igamt_export_identifier",
        "acquired_at",
        "acquired_by_role_id",
        "redistribution_status",
    ],
)
def test_profile_acquisition_metadata_rejects_blank_values(field_name: str) -> None:
    values = {
        "source_url_or_record": "record",
        "igamt_export_identifier": "export",
        "acquired_at": "2026-10-10",
        "acquired_by_role_id": "role",
        "redistribution_status": "metadata_only",
    }
    values[field_name] = ""

    with pytest.raises(ValueError, match=field_name):
        LriAcquisitionMetadata(**values)
