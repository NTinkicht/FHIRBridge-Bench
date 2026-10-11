from copy import deepcopy
from pathlib import Path

from fhirbridge.freeze_audit import assess_presealed_freeze
from fhirbridge.schema_validation import load_yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "expert_validation" / "examples" / "freeze_manifest_template.yaml"


def _ready_manifest() -> dict:
    manifest = deepcopy(load_yaml(TEMPLATE))
    manifest["manifest_id"] = "FREEZE-001"
    manifest["freeze_timestamp"] = "2026-10-06T18:00:00Z"
    manifest["protocol_version"] = "1.0.0"
    manifest["repository_commit"] = "abcdef1234567890"
    manifest["freeze_complete"] = True

    for index, component in enumerate(manifest["instrument_components"].values(), start=1):
        component["version"] = "1.0.0"
        if component["path_or_ref"] == "TO_BE_FROZEN":
            component["path_or_ref"] = f"docs/frozen-component-{index}.md"
        component["sha256"] = f"{index:064x}"

    manifest["dependencies"] = [
        {
            "name": "terminology-snapshot",
            "version": "1",
            "purpose": "terminology",
            "source_or_ref": "terminology/snapshot",
            "sha256": "a" * 64,
        },
        {
            "name": "ucum-snapshot",
            "version": "1",
            "purpose": "ucum",
            "source_or_ref": "ucum/snapshot",
            "sha256": "b" * 64,
        },
        {
            "name": "fhir-validator",
            "version": "1",
            "purpose": "fhir_validation",
            "source_or_ref": "validator/fhir",
            "sha256": "c" * 64,
        },
        {
            "name": "hl7v2-validator",
            "version": "1",
            "purpose": "hl7v2_validation",
            "source_or_ref": "validator/hl7v2",
            "sha256": "d" * 64,
        },
    ]

    manifest["instrument_component_manifest"].update(
        {
            "version": "0.1.0",
            "path_or_ref": "benchmark/instrument_component_manifest.yaml",
            "sha256": "6" * 64,
        }
    )

    manifest["reviewer_roster"].update(
        {
            "version": "1.0.0",
            "path_or_ref": "expert_validation/reviewer_roster.yaml",
            "sha256": "9" * 64,
        }
    )

    manifest["case_assignment_manifest"].update(
        {
            "version": "1.0.0",
            "path_or_ref": "expert_validation/case_assignment_manifest.yaml",
            "sha256": "8" * 64,
        }
    )
    manifest["primary_vur_hypothesis"].update(
        {
            "version": "0.1.0",
            "path_or_ref": (
                "analysis/primary_vur_hypothesis_preregistration.yaml"
            ),
            "sha256": "4" * 64,
        }
    )
    manifest["analysis_preregistration"].update(
        {
            "version": "1.0.0",
            "path_or_ref": "analysis/analysis_preregistration.yaml",
            "sha256": "7" * 64,
        }
    )
    manifest["sample_size_preregistration"].update(
        {
            "version": "1.0.0",
            "path_or_ref": "analysis/sample_size_preregistration.yaml",
            "sha256": "5" * 64,
        }
    )

    manifest["model_prompt_configuration"].update(
        {
            "version": "1.0.0",
            "path_or_ref": "models/model_prompt_freeze.yaml",
            "sha256": "6" * 64,
        }
    )

    manifest["sealed_set"].update(
        {
            "bundle_id": "SEALED-001",
            "bundle_sha256": "e" * 64,
            "case_count": 375,
            "case_manifest_sha256": "f" * 64,
        }
    )
    manifest["blinding"]["role_ids"] = [
        {"role_id": "R-INT", "role": "primary_reviewer_interoperability"},
        {"role_id": "R-CI", "role": "primary_reviewer_clinical_informatics"},
        {"role_id": "R-ADJ", "role": "adjudicator"},
        {"role_id": "R-DATA", "role": "data_custodian"},
    ]
    manifest["blinding"]["controls_verified"] = True
    manifest["acceptance_gate"] = {
        "preregistration_ref": "PREREGISTRATION.md",
        "preregistration_sha256": "1" * 64,
        "defined_before_sealed_opening": True,
        "gate_policy_summary": "Pilot-derived preregistered instrument gate.",
    }
    return manifest


def test_ready_manifest_can_authorize_first_sealed_opening() -> None:
    report = assess_presealed_freeze(_ready_manifest())

    assert report.ready_to_open_sealed_set
    assert report.blockers == ()
    assert report.warnings == ()


def test_template_is_schema_valid_but_not_operationally_ready() -> None:
    report = assess_presealed_freeze(load_yaml(TEMPLATE))

    assert not report.ready_to_open_sealed_set
    assert any("freeze_complete" in blocker for blocker in report.blockers)
    assert any("zero placeholder hash" in blocker for blocker in report.blockers)
    assert any("acceptance gate" in blocker for blocker in report.blockers)
    assert any("dependencies" in blocker for blocker in report.blockers)


def test_opened_sealed_set_cannot_pass_preopening_audit() -> None:
    manifest = _ready_manifest()
    manifest["sealed_set"]["opened"] = True
    manifest["sealed_set"]["opened_at"] = "2026-10-07T08:00:00Z"
    manifest["sealed_set"]["opened_by_role_ids"] = ["R-DATA"]

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("already marked opened" in blocker for blocker in report.blockers)
    assert any("opened_at" in blocker for blocker in report.blockers)
    assert any("opened_by_role_ids" in blocker for blocker in report.blockers)


def test_missing_blinding_role_and_control_are_blockers() -> None:
    manifest = _ready_manifest()
    manifest["blinding"]["role_ids"] = [
        role
        for role in manifest["blinding"]["role_ids"]
        if role["role"] != "primary_reviewer_clinical_informatics"
    ]
    manifest["blinding"]["verifier_verdict_hidden"] = False

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("clinical_informatics" in blocker for blocker in report.blockers)
    assert any("verifier_verdict_hidden" in blocker for blocker in report.blockers)


def test_postunsealing_instrument_change_blocks_confirmatory_reuse() -> None:
    manifest = _ready_manifest()
    manifest["post_freeze_amendments"] = [
        {
            "amendment_id": "AMD-001",
            "timestamp": "2026-10-08T09:00:00Z",
            "reason": "Verifier rule changed after the sealed set had been opened.",
            "affected_components": ["verifier"],
            "sealed_set_had_been_opened": True,
            "fresh_sealed_set_required": True,
            "replacement_manifest_id": None,
            "disposition": "REQUIRES_NEW_SEALED_SET",
        }
    ]

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("fresh untouched sealed set" in blocker for blocker in report.blockers)


def test_preopening_amendment_is_visible_but_not_automatically_fatal() -> None:
    manifest = _ready_manifest()
    manifest["post_freeze_amendments"] = [
        {
            "amendment_id": "AMD-PRE-001",
            "timestamp": "2026-10-06T19:00:00Z",
            "reason": "Corrected a documentation reference before unsealing.",
            "affected_components": ["documentation"],
            "sealed_set_had_been_opened": False,
            "fresh_sealed_set_required": False,
            "replacement_manifest_id": None,
            "disposition": "NO_EFFECT_ON_FROZEN_MEASUREMENT",
        }
    ]

    report = assess_presealed_freeze(manifest)

    assert report.ready_to_open_sealed_set
    assert report.warnings == ("pre-opening amendment recorded: AMD-PRE-001",)


def test_placeholder_manifest_bundle_and_repository_identity_block_opening() -> None:
    manifest = _ready_manifest()
    manifest["manifest_id"] = "FREEZE-TO-BE-ASSIGNED"
    manifest["repository_commit"] = "0000000"
    manifest["sealed_set"]["bundle_id"] = "SEALED-TO-BE-ASSIGNED"

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("manifest_id" in blocker for blocker in report.blockers)
    assert any("repository_commit" in blocker for blocker in report.blockers)
    assert any("bundle_id" in blocker for blocker in report.blockers)


def test_measurement_critical_dependency_requires_frozen_hash_and_no_placeholders() -> None:
    manifest = _ready_manifest()
    terminology = next(
        item
        for item in manifest["dependencies"]
        if item["purpose"] == "terminology"
    )
    terminology["version"] = "TO_BE_FROZEN"
    terminology["source_or_ref"] = "TO_BE_FROZEN"
    terminology["sha256"] = None

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("placeholder version" in blocker for blocker in report.blockers)
    assert any("placeholder source" in blocker for blocker in report.blockers)
    assert any("lacks a frozen SHA-256" in blocker for blocker in report.blockers)


def test_acceptance_gate_placeholder_reference_or_hash_blocks_opening() -> None:
    manifest = _ready_manifest()
    manifest["acceptance_gate"]["preregistration_ref"] = "TO_BE_FROZEN"
    manifest["acceptance_gate"]["preregistration_sha256"] = "0" * 64
    manifest["acceptance_gate"]["gate_policy_summary"] = "TO_BE_FROZEN"

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("preregistration_ref" in blocker for blocker in report.blockers)
    assert any("preregistration_sha256" in blocker for blocker in report.blockers)
    assert any("policy summary" in blocker for blocker in report.blockers)


def test_unfrozen_reviewer_roster_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["reviewer_roster"]["version"] = "TO_BE_FROZEN"
    manifest["reviewer_roster"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("reviewer_roster" in blocker for blocker in report.blockers)


def test_unfrozen_case_assignment_manifest_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["case_assignment_manifest"]["version"] = "TO_BE_FROZEN"
    manifest["case_assignment_manifest"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("case_assignment_manifest" in blocker for blocker in report.blockers)


def test_unfrozen_analysis_preregistration_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["analysis_preregistration"]["version"] = "TO_BE_FROZEN"
    manifest["analysis_preregistration"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any("analysis_preregistration" in blocker for blocker in report.blockers)


def test_unfrozen_model_prompt_configuration_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["model_prompt_configuration"]["version"] = "TO_BE_FROZEN"
    manifest["model_prompt_configuration"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "model_prompt_configuration" in blocker
        for blocker in report.blockers
    )


def test_unfrozen_sample_size_preregistration_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["sample_size_preregistration"]["version"] = "TO_BE_FROZEN"
    manifest["sample_size_preregistration"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "sample_size_preregistration" in blocker
        for blocker in report.blockers
    )


def test_unfrozen_component_boundary_manifest_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["instrument_component_manifest"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "instrument_component_manifest" in blocker
        for blocker in report.blockers
    )


def test_malformed_component_hash_blocks_opening() -> None:
    manifest = _ready_manifest()
    manifest["reviewer_roster"]["sha256"] = "not-a-sha256"

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "reviewer_roster lacks a frozen SHA-256" in blocker
        for blocker in report.blockers
    )


def test_malformed_repository_commit_blocks_opening() -> None:
    manifest = _ready_manifest()
    manifest["repository_commit"] = "not-a-commit"

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "repository_commit is missing, malformed, or placeholder" == blocker
        for blocker in report.blockers
    )


def test_malformed_critical_dependency_entry_blocks_opening() -> None:
    manifest = _ready_manifest()
    manifest["dependencies"].append("bad-dependency-entry")

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert "dependency entry is malformed" in report.blockers


def test_distinct_artifacts_may_share_a_measurement_purpose() -> None:
    manifest = _ready_manifest()
    additional = dict(manifest["dependencies"][0])
    additional["name"] = "independent-hl7-terminology-package"
    additional["sha256"] = "c" * 64
    manifest["dependencies"].append(additional)

    report = assess_presealed_freeze(manifest)

    assert not any(
        "duplicate measurement-critical dependency identity" in blocker
        for blocker in report.blockers
    )


def test_duplicate_critical_dependency_identity_blocks_opening() -> None:
    manifest = _ready_manifest()
    duplicate = dict(manifest["dependencies"][0])
    duplicate["sha256"] = "c" * 64
    manifest["dependencies"].append(duplicate)

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "duplicate measurement-critical dependency identity" in blocker
        for blocker in report.blockers
    )


def test_missing_artifact_identity_fields_block_opening() -> None:
    manifest = _ready_manifest()
    manifest["analysis_preregistration"]["artifact_id"] = ""
    manifest["analysis_preregistration"]["path_or_ref"] = ""

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "analysis_preregistration lacks artifact_id" in blocker
        for blocker in report.blockers
    )
    assert any(
        "analysis_preregistration has missing/placeholder path_or_ref" in blocker
        for blocker in report.blockers
    )


def test_unfrozen_primary_vur_hypothesis_blocks_sealed_opening() -> None:
    manifest = _ready_manifest()
    manifest["primary_vur_hypothesis"]["version"] = "TO_BE_FROZEN"
    manifest["primary_vur_hypothesis"]["sha256"] = "0" * 64

    report = assess_presealed_freeze(manifest)

    assert not report.ready_to_open_sealed_set
    assert any(
        "primary_vur_hypothesis" in blocker
        for blocker in report.blockers
    )
