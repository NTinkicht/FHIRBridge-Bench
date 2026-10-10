from copy import deepcopy

import pytest
import yaml

from fhirbridge.tooling_manifest import (
    assert_confirmatory_frozen,
    assess_freeze_readiness,
    freeze_readiness_to_dict,
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
    assert readiness.unresolved_paths == (
        "structural_validation.hl7v2.profile_artifact",
        "structural_validation.hl7v2.profile_artifact_sha256",
        "structural_validation.hl7v2.validator_runtime_classpath_sha256",
    )
    assert readiness.false_boolean_paths == (
        "structural_validation.hl7v2.profile_validation_qualification_passed",
    )


def test_candidate_versions_are_pinned_to_documented_protocol_choices() -> None:
    manifest = _manifest()

    assert manifest["terminology"]["loinc"]["content_version"] == "2.83"
    assert (
        manifest["terminology"]["loinc"]["local_snapshot_sha256"]
        == "5de1463f0fe65d6c97867153b43151a07ce3f8c8a86de681f98e110008032aba"
    )
    assert (
        manifest["terminology"]["loinc"]["release_zip_sha256"]
        == "077a0718e87d8309ffe3a673f75b836a8e783dc36a646413ef97c71c12eab27e"
    )
    assert (
        manifest["terminology"]["loinc"]["local_provider_qualification_passed"]
        is True
    )
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
    assert (
        manifest["units"]["ucum"]["implementation_commit"]
        == "db9d22ade3f0f4a667b45817b85a9ac4534e4224"
    )
    assert manifest["units"]["ucum"]["official_functional_tests_passed"] is True
    assert manifest["units"]["ucum"]["official_functional_tests_count"] == 573
    assert manifest["units"]["ucum"]["project_lab_conversion_matrix_passed"] is True
    assert (
        manifest["units"]["ucum"]["qualification_workflow_run_id"]
        == 37780787093
    )
    assert (
        manifest["units"]["ucum"]["functional_tests_git_blob_sha"]
        == "76a7fb03cb1009639786955a53c1a6426383cb8d"
    )
    assert (
        manifest["units"]["ucum"]["functional_tests_sha256"]
        == "3b3feb9d8ecfe8958da69b1afcd25572e3f8d80a36bfcbcda4834a10a0eeef0d"
    )
    assert manifest["units"]["ucum"]["functional_tests_history_date"] == "2014-08-18"
    assert manifest["terminology"]["hl7_terminology"]["version"] == "7.4.0"
    assert (
        manifest["terminology"]["hl7_terminology"]["package_sha256"]
        == "1dc558c204f5ee1f2b96ab9a8cd83d0811475b08a4e06a7c2bcea55d1ab116ed"
    )
    assert manifest["terminology"]["hl7_terminology"]["qualification_passed"] is True
    assert (
        manifest["terminology"]["hl7_terminology"]["qualification_workflow_run_id"]
        == 37953147893
    )
    assert (
        manifest["structural_validation"]["fhir"]["validator_wrapper_version"]
        == "1.0.82"
    )
    assert (
        manifest["structural_validation"]["fhir"]["validator_artifact_sha256"]
        == "6819cfee60dddc5b93baf6252cb51078facf5021ad56ccabf0a4404309111e80"
    )
    assert manifest["structural_validation"]["fhir"]["core_version"] == "6.10.0"
    assert manifest["structural_validation"]["fhir"]["validator_cli_version"] == "6.10.0"
    assert (
        manifest["structural_validation"]["fhir"]["validator_cli_artifact_sha256"]
        == "fc663ae55dd31bbfde19788dddfb49cacbeebc3c64498fa7b7779df90000434b"
    )
    assert manifest["structural_validation"]["fhir"]["runtime"] == "Java_17"
    assert (
        manifest["structural_validation"]["fhir"]["profile_validation_qualification_passed"]
        is True
    )
    assert manifest["structural_validation"]["fhir"]["qualification_fixture_count"] == 4
    assert (
        manifest["structural_validation"]["fhir"]["qualification_zero_error_fixture_count"]
        == 4
    )
    assert (
        manifest["structural_validation"]["fhir"]["qualification_workflow_run_id"]
        == 37782284261
    )
    assert (
        manifest["structural_validation"]["fhir"]["qualification_artifact_sha256"]
        == "e874a9cf28599a79e260ac20d8ef2b4bd778b966c7e44559f3134e288d6e8ca0"
    )
    assert (
        manifest["structural_validation"]["fhir"]["package_cache_manifest_sha256"]
        == "aea8f39ef73056de5f0eec423080c5a9edc55acf1b034e1aa67d4ae2f307827c"
    )
    assert (
        manifest["structural_validation"]["fhir"]["package_cache_manifest_source_run_id"]
        == 37941158582
    )
    assert (
        manifest["structural_validation"]["fhir"]["package_cache_directory_count"]
        == 22
    )
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
    assert (
        manifest["structural_validation"]["hl7v2"]["validator_repository_commit"]
        == "eeac90c5f88dca3018992005232acdf3da644d88"
    )
    assert (
        manifest["structural_validation"]["hl7v2"][
            "validator_runtime_classpath_sha256"
        ]
        == "unresolved"
    )
    assert (
        manifest["structural_validation"]["hl7v2"][
            "validator_runtime_hash_method"
        ]
        == "stable_label_sha256_size_manifest_v1"
    )
    assert manifest["structural_validation"]["hl7v2"]["harness_compilation_passed"] is True
    assert (
        manifest["structural_validation"]["hl7v2"]["legacy_differential_execution_passed"]
        is True
    )
    assert manifest["structural_validation"]["hl7v2"]["legacy_differential_error_total"] == 14
    assert (
        manifest["structural_validation"]["hl7v2"]["legacy_differential_workflow_run_id"]
        == 37950773310
    )
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



def test_freeze_readiness_export_counts_current_candidate_blockers() -> None:
    readiness = assess_freeze_readiness(_manifest())
    exported = freeze_readiness_to_dict(readiness)

    assert exported["ready"] is False
    assert exported["manifest_status"] == "candidate"
    assert exported["blocker_count"] == (
        len(exported["unresolved_paths"]) + len(exported["false_boolean_paths"])
    )
    assert exported["blocker_count"] == 4
    assert "structural_validation.hl7v2.profile_artifact" in exported["unresolved_paths"]
