"""Build a machine-filled candidate freeze record from an inspected LRI archive."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hl7v2_profile_archive import ProfileArchiveInspection


@dataclass(frozen=True)
class LriAcquisitionMetadata:
    source_url_or_record: str
    igamt_export_identifier: str
    acquired_at: str
    acquired_by_role_id: str
    redistribution_status: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("source_url_or_record", self.source_url_or_record),
            ("igamt_export_identifier", self.igamt_export_identifier),
            ("acquired_at", self.acquired_at),
            ("acquired_by_role_id", self.acquired_by_role_id),
            ("redistribution_status", self.redistribution_status),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")


def build_lri_profile_pin_candidate(
    inspection: ProfileArchiveInspection,
    acquisition: LriAcquisitionMetadata,
) -> dict[str, Any]:
    """Return only machine-verifiable fields for the profile freeze record.

    Edition/errata provenance and independent review flags intentionally remain
    false. A cryptographically inspected archive cannot prove by itself that it
    is the publication named in the protocol.
    """

    files = {
        item.name: item
        for item in inspection.manifest.files
    }
    profile = files.get("PROFILE.xml")
    if profile is None:
        raise ValueError("inspection manifest does not contain PROFILE.xml")

    return {
        "acquisition": {
            "source_url_or_record": acquisition.source_url_or_record,
            "igamt_export_identifier": acquisition.igamt_export_identifier,
            "acquired_at": acquisition.acquired_at,
            "acquired_by_role_id": acquisition.acquired_by_role_id,
            "redistribution_status": acquisition.redistribution_status,
        },
        "bundle": {
            "archive_sha256": inspection.archive_sha256,
            "source_directory_in_archive": inspection.source_directory,
            "aggregate_sha256": inspection.manifest.aggregate_sha256,
            "profile_xml_sha256": profile.sha256,
            "component_files": [
                {
                    "name": item.name,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in inspection.manifest.files
            ],
        },
        "identity_verification": {
            "profile_xml_hl7_version": inspection.identity.hl7_version,
            "profile_xml_message_type": inspection.identity.message_type,
            "profile_xml_event_type": inspection.identity.event_type,
            "profile_xml_message_structure": inspection.identity.message_structure,
            "selected_message_identifier": inspection.selected_message.identifier,
            "profile_identity_guard_passed": True,
            "edition_5_evidence_checked": False,
            "errata_2024dec_evidence_checked": False,
            "independent_profile_provenance_reviewed": False,
        },
    }
