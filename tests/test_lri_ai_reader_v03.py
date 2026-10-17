"""Mistral v0.3 custody using synthetic candidates only, not HL7 source."""

import json
import os
import runpy
import sys
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_ai_reader_v03 import preflight_mistral_reader_a_v03
from fhirbridge.lri_extraction_lock import verify_response_lock
from fhirbridge.lri_rule_level_extraction_v03 import (
    create_v03_response_lock,
    verify_v03_response_lock,
)

_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/"
    "rule_level_extraction_v03_blank.yaml"
)
_SCRIPT = Path(
    "qualification/hl7v2/required_element_review/intake_mistral_reader_a_v03.py"
)


def _source() -> dict:
    doc = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    doc["extraction_id"] = "MISTRAL-V03-SYNTHETIC-RUN-001"
    doc["extractor"]["extractor_id"] = "MISTRAL-READER-A"
    doc["extractor"]["role"] = "AI_preliminary_extractor"
    doc["extractor"]["prior_project_involvement"] = "Mistral AI-assisted synthetic test"
    doc["notes"] = (
        "Mistral AI-assisted; model_id=mistral-test-2026; "
        "model_version=synthetic-0001; source not actually reviewed"
    )
    doc["entries"] = [
        {
            "candidate_rule_id": f"AI-{suffix}",
            "rule_kind": "CONDITIONAL_PREDICATE",
            "locus": "OBR-3",
            "element_kind": "field",
            "usage": "C",
            "cardinality": "1..1",
            "datatype": "EI",
            "max_length": None,
            "condition": f"SYNTHETIC CONDITION {suffix}",
            "value_set_or_binding_ref": None,
            "source_grounding_classification": "SOURCE_FACT",
            "classification_rationale": "Synthetic only",
            "evidence": [f"Synthetic citation {suffix}; not official source"],
        }
        for suffix in ("A", "B")
    ]
    doc["extraction_complete"] = False
    return doc


def _raw(doc=None) -> bytes:
    return yaml.safe_dump(
        doc if doc is not None else _source(), sort_keys=False
    ).encode("utf-8")


def _cli():
    return runpy.run_path(str(_SCRIPT))["main"]


def test_two_rules_same_locus_receive_v03_lock_without_scientific_approval() -> None:
    raw = _raw()
    receipt = preflight_mistral_reader_a_v03(raw, source_use_authorized=True)
    assert receipt.status == "PRIVATE_AI_V03_RULE_LEVEL_NOT_HUMAN_VALIDATED"
    assert receipt.original_response_sha256 == sha256(raw).hexdigest()
    assert receipt.metadata_schema_ready is False
    lock = receipt.original_response_lock
    assert lock["lock_schema_version"] == "0.3.0"
    assert lock["candidate_rule_count"] == 2
    assert lock["metadata_ready"] is False
    assert lock["qualified_G1"] is False
    restored = verify_v03_response_lock(raw, lock)
    assert [r["locus"] for r in restored["entries"]] == ["OBR-3", "OBR-3"]
    assert receipt.independent_human_extraction_received is False
    assert receipt.requirements_denominator_qualified is False
    assert receipt.G1_qualified is False
    assert receipt.confirmatory_permission is False
    with pytest.raises(ValueError, match="invalid extraction response lock version"):
        verify_response_lock(raw, lock)


def test_fake_complete_looking_ai_evidence_never_grants_g1() -> None:
    doc = _source()
    doc["extraction_complete"] = True
    result = preflight_mistral_reader_a_v03(
        _raw(doc), source_use_authorized=True
    )
    assert result.metadata_schema_ready is True
    assert result.G1_qualified is False
    assert result.requirements_denominator_qualified is False
    assert result.original_response_lock["independently_verified_completeness"] is False


@pytest.mark.parametrize("allow", [False, None, "", "true", 1, 0])
def test_source_use_permission_declaration_must_be_real_boolean(allow) -> None:
    with pytest.raises(ValueError, match="source-use authorization"):
        preflight_mistral_reader_a_v03(_raw(), source_use_authorized=allow)


@pytest.mark.parametrize("role", ["human", "independent_LRI_required_element_extractor", ""])
def test_ai_cannot_impersonate_a_human_reviewer(role: str) -> None:
    doc = _source()
    doc["extractor"]["role"] = role
    with pytest.raises(ValueError, match="AI Reader A"):
        preflight_mistral_reader_a_v03(_raw(doc), source_use_authorized=True)


@pytest.mark.parametrize("metadata", [
    "Mistral AI-assisted",
    "Mistral AI-assisted; model_id=mistral-model-001",
    "Mistral AI-assisted; model_version=2026-0001",
    "Mistral AI-assisted; model_id=mistral-model-001; model_version=latest",
    "Mistral AI-assisted; model_id=unknown; model_version=2026-0001",
    "Mistral AI-assisted; model_id=mistral-model-001; model_version=2026-0001; model_version=2026-0002",
])
def test_missing_floating_or_ambiguous_model_provenance_fails(metadata: str) -> None:
    doc = _source()
    doc["notes"] = metadata
    with pytest.raises(ValueError, match="model_id|model ID/version"):
        preflight_mistral_reader_a_v03(_raw(doc), source_use_authorized=True)


@pytest.mark.parametrize("flag", [
    "other_extractor_output_seen_before_completion",
    "project_required_element_inventory_seen_before_completion",
    "renderer_output_used_as_requirement_evidence",
])
def test_truthfully_exposed_original_quarantines_and_keeps_exact_hash(flag: str) -> None:
    doc = _source()
    doc["independence"][flag] = True
    raw = _raw(doc)
    result = preflight_mistral_reader_a_v03(raw, source_use_authorized=True)
    assert result.status == "PRIVATE_AI_V03_EXPOSURE_QUARANTINED_NOT_ELIGIBLE"
    assert result.original_response_sha256 == sha256(raw).hexdigest()
    quarantine = result.original_response_lock
    assert quarantine["status"] == "AI_RULE_LEVEL_V03_EXPOSURE_QUARANTINED"
    assert quarantine["disclosed_or_missing_independence_flags"] == [flag]
    assert result.metadata_schema_ready is False
    assert result.G1_qualified is False
    with pytest.raises(ValueError, match="v0.3 original bytes or lock metadata changed|invalid v0.3 lock version"):
        verify_v03_response_lock(raw, quarantine)


def test_missing_isolation_disclosure_is_not_assumed_false() -> None:
    doc = _source()
    del doc["independence"]["renderer_output_used_as_requirement_evidence"]
    result = preflight_mistral_reader_a_v03(
        _raw(doc), source_use_authorized=True
    )
    assert result.status == "PRIVATE_AI_V03_EXPOSURE_QUARANTINED_NOT_ELIGIBLE"
    assert result.original_response_lock["disclosed_or_missing_independence_flags"] == [
        "renderer_output_used_as_requirement_evidence"
    ]


def test_duplicate_candidate_ids_and_same_rule_content_fail_closed() -> None:
    doc = _source()
    doc["entries"][1]["candidate_rule_id"] = doc["entries"][0]["candidate_rule_id"]
    with pytest.raises(ValueError, match="duplicate candidate rule ID"):
        preflight_mistral_reader_a_v03(_raw(doc), source_use_authorized=True)
    doc = _source()
    duplicate = deepcopy(doc["entries"][0])
    duplicate["candidate_rule_id"] = "NEW-INDEPENDENT-ID"
    doc["entries"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate substantive candidate"):
        preflight_mistral_reader_a_v03(_raw(doc), source_use_authorized=True)


def test_legacy_v02_original_not_silently_upgraded_into_v03() -> None:
    raw = Path(
        "qualification/hl7v2/required_element_review/examples/extraction_template.yaml"
    ).read_bytes()
    with pytest.raises(ValueError, match="not explicit v0.3 extraction"):
        preflight_mistral_reader_a_v03(raw, source_use_authorized=True)


def test_byte_changes_invalidate_v03_original_response_lock() -> None:
    raw = _raw()
    result = preflight_mistral_reader_a_v03(raw, source_use_authorized=True)
    with pytest.raises(ValueError, match="original bytes or lock metadata changed"):
        verify_v03_response_lock(raw + b"\n#changed", result.original_response_lock)
    assert create_v03_response_lock(raw)["response_sha256"] == sha256(raw).hexdigest()


def test_output_cannot_be_mutated_into_human_qualification() -> None:
    result = preflight_mistral_reader_a_v03(_raw(), source_use_authorized=True)
    with pytest.raises(FrozenInstanceError):
        result.G1_qualified = True
    with pytest.raises(FrozenInstanceError):
        result.confirmatory_permission = True


def test_v03_private_cli_exclusive_permissions_and_no_original_stdout(
    tmp_path, monkeypatch, capsys
) -> None:
    raw = _raw()
    original = tmp_path / "ai-original.yaml"
    receipt = tmp_path / "ai-original.lock.json"
    original.write_bytes(raw)
    monkeypatch.setattr(sys, "argv", [
        "intake_mistral_reader_a_v03.py", str(original), str(receipt),
        "--source-use-authorized",
    ])
    assert _cli()() == 0
    obj = json.loads(receipt.read_text(encoding="utf-8"))
    assert verify_v03_response_lock(raw, obj)["extractor"]["role"] == "AI_preliminary_extractor"
    if os.name == "posix":
        assert receipt.stat().st_mode & 0o777 == 0o600
    log = capsys.readouterr().out
    assert "SYNTHETIC CONDITION" not in log
    assert "PRIVATE_AI_V03_RULE_LEVEL_NOT_HUMAN_VALIDATED" in log
    assert _cli()() == 1
    assert json.loads(receipt.read_text(encoding="utf-8")) == obj


def test_v03_cli_exposure_returns_nonzero_but_keeps_lock(
    tmp_path, monkeypatch
) -> None:
    doc = _source()
    doc["independence"]["other_extractor_output_seen_before_completion"] = True
    original = tmp_path / "ai-exposed.yaml"
    receipt = tmp_path / "ai-exposed.lock.json"
    original.write_bytes(_raw(doc))
    monkeypatch.setattr(sys, "argv", [
        "intake_mistral_reader_a_v03.py", str(original), str(receipt),
        "--source-use-authorized",
    ])
    assert _cli()() == 2
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == (
        "AI_RULE_LEVEL_V03_EXPOSURE_QUARANTINED"
    )


def test_v03_cli_rejects_public_repo_paths_and_unauthorized_use(
    tmp_path, monkeypatch
) -> None:
    outside = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", [
        "intake_mistral_reader_a_v03.py",
        str(_TEMPLATE), str(outside), "--source-use-authorized",
    ])
    assert _cli()() == 1
    assert not outside.exists()
    original = tmp_path / "ai-original.yaml"
    original.write_bytes(_raw())
    monkeypatch.setattr(sys, "argv", [
        "intake_mistral_reader_a_v03.py", str(original), str(outside)
    ])
    assert _cli()() == 1
    assert not outside.exists()
