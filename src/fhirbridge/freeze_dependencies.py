"""Derive measurement-critical freeze dependencies from frozen tooling pins."""

from __future__ import annotations

from typing import Any

from .tooling_manifest import assert_confirmatory_frozen


def _string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def build_freeze_dependencies(
    tooling: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build deterministic dependency records only from a frozen tooling manifest."""

    assert_confirmatory_frozen(tooling)

    terminology = tooling["terminology"]
    units = tooling["units"]
    validation = tooling["structural_validation"]

    loinc = terminology["loinc"]
    tho = terminology["hl7_terminology"]
    ucum = units["ucum"]
    fhir = validation["fhir"]
    v2 = validation["hl7v2"]

    dependencies = [
        {
            "name": "LOINC local terminology snapshot",
            "version": _string(
                loinc.get("content_version"),
                label="LOINC content_version",
            ),
            "purpose": "terminology",
            "source_or_ref": _string(
                loinc.get("official_download_filename"),
                label="LOINC official_download_filename",
            ),
            "sha256": _string(
                loinc.get("local_snapshot_sha256"),
                label="LOINC local_snapshot_sha256",
            ),
        },
        {
            "name": "HL7 Terminology package",
            "version": _string(
                tho.get("version"),
                label="HL7 Terminology version",
            ),
            "purpose": "terminology",
            "source_or_ref": _string(
                tho.get("package"),
                label="HL7 Terminology package",
            ),
            "sha256": _string(
                tho.get("package_sha256"),
                label="HL7 Terminology package_sha256",
            ),
        },
        {
            "name": "UCUM essence",
            "version": _string(
                ucum.get("content_version"),
                label="UCUM content_version",
            ),
            "purpose": "ucum",
            "source_or_ref": _string(
                ucum.get("essence_source"),
                label="UCUM essence_source",
            ),
            "sha256": _string(
                ucum.get("essence_sha256"),
                label="UCUM essence_sha256",
            ),
        },
        {
            "name": "HL7 FHIR Validator CLI",
            "version": _string(
                fhir.get("validator_cli_version"),
                label="FHIR validator_cli_version",
            ),
            "purpose": "fhir_validation",
            "source_or_ref": _string(
                fhir.get("validator_cli_artifact_source"),
                label="FHIR validator_cli_artifact_source",
            ),
            "sha256": _string(
                fhir.get("validator_cli_artifact_sha256"),
                label="FHIR validator_cli_artifact_sha256",
            ),
        },
        {
            "name": "US Core validation package cache",
            "version": _string(
                fhir.get("packages", {}).get("us_core"),
                label="FHIR US Core package",
            ),
            "purpose": "fhir_validation",
            "source_or_ref": _string(
                fhir.get("package_dependency_source"),
                label="FHIR package_dependency_source",
            ),
            "sha256": _string(
                fhir.get("package_cache_manifest_sha256"),
                label="FHIR package_cache_manifest_sha256",
            ),
        },
        {
            "name": "HL7 v2.5.1 LRI Edition 5 profile validation bundle",
            "version": (
                f"{_string(v2.get('target'), label='HL7v2 target')}"
                f"+{_string(v2.get('errata'), label='HL7v2 errata')}"
                f"|validator={_string(v2.get('validator_version'), label='HL7v2 validator_version')}"
            ),
            "purpose": "hl7v2_validation",
            "source_or_ref": (
                f"{_string(v2.get('profile_artifact'), label='HL7v2 profile_artifact')}"
                f"|{_string(v2.get('source_repository'), label='HL7v2 source_repository')}"
                f"@{_string(v2.get('validator_repository_commit'), label='HL7v2 validator_repository_commit')}"
            ),
            "sha256": _string(
                v2.get("profile_artifact_sha256"),
                label="HL7v2 profile_artifact_sha256",
            ),
        },
    ]

    # Schema-level SHA validation happens in the freeze-manifest validator. This
    # layer additionally rejects duplicated semantic dependency records.
    identities = [(item["name"], item["version"]) for item in dependencies]
    if len(identities) != len(set(identities)):
        raise ValueError("derived freeze dependencies contain duplicates")
    return dependencies
