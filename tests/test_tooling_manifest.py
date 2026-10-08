from copy import deepcopy

import pytest
import yaml

from fhirbridge.tooling_manifest import (
    assert_confirmatory_frozen,
    assess_freeze_readiness,
)

_MANIFEST_PATH = "benchmark/tooling_versions.yaml"


def _manifest() -> dict:
    with open(_MANIFEST_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _set_path(document: dict, dotted_path: str, value) -> None:
    current = document
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def test_candidate_manifest_is_explicitly_not_freeze_ready() -> None:
    readiness = assess_freeze_readiness(_manifest())

    assert readiness.manifest_status == "candidate"
    assert not readiness.ready
    assert "terminology.loinc.local_snapshot_sha256" in readiness.unresolved_paths
    assert "structural_validation.hl7v2.profile_artifact" in readiness.unresolved_paths
    assert (
        "units.ucum.official_functional_tests_passed"
        in readiness.false_boolean_paths
    )
    assert (
        "terminology.loinc.local_provider_qualification_passed"
        in readiness.false_boolean_paths
    )
    assert (
        "structural_validation.fhir.profile_validation_qualification_passed"
        in readiness.false_boolean_paths
    )
    assert (
        "structural_validation.hl7v2.profile_validation_qualification_passed"
        in readiness.false_boolean_paths
    )


def test_candidate_versions_are_pinned_to_documented_protocol_choices() -> None:
    manifest = _manifest()

    assert manifest["terminology"]["loinc"]["content_version"] == "2.83"
    assert manifest["units"]["ucum"]["content_version"] == "2.2"
    assert manifest["units"]["ucum"]["essence_revision_date"] == "2024-06-17"
    assert (
        manifest["units"]["ucum"]["essence_sha256"]
        == "dfccea1b5dc284245ebae97edd1dc03c45864da4e87df55bc9851797b4fd0b61"
    )
    assert (
        manifest["units"]["ucum"]["essence_git_blob_sha"]
        == "ec61d23ce68da34bf10726daef7b33d70bbc1b4f"
    )
    assert manifest["units"]["ucum"]["implementation"] == "org.fhir:ucum"
    assert manifest["units"]["ucum"]["implementation_version"] == "1.0.10"
    assert manifest["terminology"]["hl7_terminology"]["version"] == "7.4.0"
    assert (
        manifest["structural_validation"]["fhir"]["validator_wrapper_version"]
        == "1.0.82"
    )
    assert (
        manifest["structural_validation"]["fhir"]["validator_artifact_sha256"]
        == "6819cfee60dddc5b93baf6252cb51078facf5021ad56ccabf0a4404309111e80"
    )
    assert manifest["structural_validation"]["fhir"]["core_version"] == "6.10.0"
    assert manifest["structural_validation"]["fhir"]["runtime"] == "Java_17"
    assert (
        manifest["structural_validation"]["fhir"]["packages"]["fhir_r4"]
        == "hl7.fhir.r4.core#4.0.1"
    )
    assert (
        manifest["structural_validation"]["fhir"]["packages"]["us_core"]
        == "hl7.fhir.us.core#9.0.0"
    )
    assert (
        manifest["structural_validation"]["fhir"]["packages"]["hl7_terminology_r4"]
        == "hl7.terminology.r4#7.1.0"
    )
    assert (
        manifest["structural_validation"]["hl7v2"]["validator"]
        == "gov.cdc:lib-hl7v2-nist-validator"
    )
    assert manifest["structural_validation"]["hl7v2"]["validator_version"] == "1.5.0"
    assert manifest["structural_validation"]["hl7v2"]["nist_engine_version"] == "1.7.3"
    assert manifest["network_policy"]["live_terminology_services"] == "audit_only"
    assert (
        manifest["network_policy"]["hosted_hl7v2_validation_services"] == "audit_only"
    )


def test_manifest_cannot_claim_frozen_with_unresolved_dependencies() -> None:
    manifest = _manifest()
    manifest["manifest"]["status"] = "frozen"

    with pytest.raises(ValueError, match="cannot be marked frozen"):
        assess_freeze_readiness(manifest)


def test_fully_resolved_manifest_can_pass_freeze_gate() -> None:
    manifest = deepcopy(_manifest())
    gate = manifest["freeze_gate"]

    for path in gate["required_before_status_frozen"]:
        _set_path(manifest, path, f"resolved:{path}")
    for path in gate["required_boolean_true_before_status_frozen"]:
        _set_path(manifest, path, True)
    manifest["manifest"]["status"] = "frozen"

    readiness = assess_freeze_readiness(manifest)

    assert readiness.ready
    assert readiness.unresolved_paths == ()
    assert readiness.false_boolean_paths == ()
    assert_confirmatory_frozen(manifest)


def test_confirmatory_gate_rejects_complete_but_unfrozen_manifest() -> None:
    manifest = deepcopy(_manifest())
    gate = manifest["freeze_gate"]

    for path in gate["required_before_status_frozen"]:
        _set_path(manifest, path, f"resolved:{path}")
    for path in gate["required_boolean_true_before_status_frozen"]:
        _set_path(manifest, path, True)

    with pytest.raises(ValueError, match="status must be frozen"):
        assert_confirmatory_frozen(manifest)


def test_missing_freeze_gate_path_is_rejected() -> None:
    manifest = deepcopy(_manifest())
    manifest["freeze_gate"]["required_before_status_frozen"].append(
        "structural_validation.fhir.nonexistent_field"
    )

    with pytest.raises(ValueError, match="manifest path not found"):
        assess_freeze_readiness(manifest)
