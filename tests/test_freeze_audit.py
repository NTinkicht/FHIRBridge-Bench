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

    manifest["reviewer_roster"].update(
        {
            "version": "1.0.0",
            "path_or_ref": "expert_validation/reviewer_roster.yaml",
            "sha256": "9" * 64,
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
