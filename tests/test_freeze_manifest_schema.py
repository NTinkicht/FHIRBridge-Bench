from copy import deepcopy
from pathlib import Path

import yaml

from fhirbridge.schema_validation import load_yaml, validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "expert_validation" / "schema" / "freeze_manifest.schema.json"
TEMPLATE = ROOT / "expert_validation" / "examples" / "freeze_manifest_template.yaml"


def _write_yaml(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_nonassertive_freeze_manifest_template_matches_schema() -> None:
    assert validate_document(TEMPLATE, SCHEMA) == []


def test_freeze_manifest_requires_all_measurement_critical_components(tmp_path: Path) -> None:
    manifest = deepcopy(load_yaml(TEMPLATE))
    del manifest["instrument_components"]["hl7v2_lifter"]

    problems = validate_document(
        _write_yaml(tmp_path, "missing-lifter.yaml", manifest),
        SCHEMA,
    )

    assert problems
    assert any("hl7v2_lifter" in problem.message for problem in problems)


def test_frozen_artifact_hash_must_be_sha256(tmp_path: Path) -> None:
    manifest = deepcopy(load_yaml(TEMPLATE))
    manifest["instrument_components"]["verifier"]["sha256"] = "not-a-hash"

    problems = validate_document(
        _write_yaml(tmp_path, "bad-artifact-hash.yaml", manifest),
        SCHEMA,
    )

    assert problems


def test_sealed_split_uses_controlled_vocabulary(tmp_path: Path) -> None:
    manifest = deepcopy(load_yaml(TEMPLATE))
    manifest["sealed_set"]["split"] = "test-ish"

    problems = validate_document(
        _write_yaml(tmp_path, "bad-split.yaml", manifest),
        SCHEMA,
    )

    assert problems
    assert any("test-ish" in problem.message for problem in problems)


def test_blinding_role_uses_controlled_vocabulary(tmp_path: Path) -> None:
    manifest = deepcopy(load_yaml(TEMPLATE))
    manifest["blinding"]["role_ids"] = [
        {"role_id": "R1", "role": "model_developer"}
    ]

    problems = validate_document(
        _write_yaml(tmp_path, "bad-role.yaml", manifest),
        SCHEMA,
    )

    assert problems
    assert any("model_developer" in problem.message for problem in problems)


def test_acceptance_gate_must_record_presealed_preregistration(tmp_path: Path) -> None:
    manifest = deepcopy(load_yaml(TEMPLATE))
    manifest["acceptance_gate"] = {
        "preregistration_ref": "PREREGISTRATION.md",
        "preregistration_sha256": "a" * 64,
        "defined_before_sealed_opening": True,
        "gate_policy_summary": "Pilot-derived sensitivity and PPV gate.",
    }

    assert (
        validate_document(
            _write_yaml(tmp_path, "with-gate.yaml", manifest),
            SCHEMA,
        )
        == []
    )


def test_postfreeze_amendment_disposition_is_constrained(tmp_path: Path) -> None:
    manifest = deepcopy(load_yaml(TEMPLATE))
    manifest["post_freeze_amendments"] = [
        {
            "amendment_id": "AMD-001",
            "timestamp": "2026-10-06T18:00:00Z",
            "reason": "Verifier logic changed after sealed opening.",
            "affected_components": ["verifier"],
            "sealed_set_had_been_opened": True,
            "fresh_sealed_set_required": True,
            "replacement_manifest_id": null,
            "disposition": "IGNORE_AND_CONTINUE",
        }
    ]

    problems = validate_document(
        _write_yaml(tmp_path, "bad-amendment.yaml", manifest),
        SCHEMA,
    )

    assert problems
    assert any("IGNORE_AND_CONTINUE" in problem.message for problem in problems)
