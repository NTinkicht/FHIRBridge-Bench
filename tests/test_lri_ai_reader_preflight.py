"""Private Mistral Reader A intake: no authentic reviewer data in tests."""

import json
import os
import runpy
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_ai_reader_preflight import preflight_mistral_reader_a
from fhirbridge.lri_extraction_lock import verify_response_lock


def _response() -> bytes:
    with open(
        "qualification/hl7v2/required_element_review/examples/extraction_template.yaml",
        encoding="utf-8",
    ) as stream:
        doc = yaml.safe_load(stream)
    doc["extraction_id"] = "MISTRAL-A-SYNTHETIC-001"
    doc["extractor"]["extractor_id"] = "MISTRAL-READER-A"
    doc["extractor"]["role"] = "AI_preliminary_extractor"
    doc["extractor"]["prior_project_involvement"] = (
        "Mistral AI-assisted blind candidate extraction; synthetic test"
    )
    doc["notes"] = (
        "Mistral AI-assisted; model_id=mistral-synthetic-test; "
        "model_version=synthetic-test-v1; unreviewed and not human-attested"
    )
    doc["entries"][0]["locus"] = "OBR-3"
    doc["entries"][0]["element_kind"] = "field"
    doc["entries"][0]["usage"] = "UNKNOWN"
    doc["entries"][0]["cardinality"] = "TO_BE_EXTRACTED"
    doc["entries"][0]["source_grounding_classification"] = "UNRESOLVED"
    doc["extraction_complete"] = False
    return yaml.safe_dump(doc, sort_keys=False).encode("utf-8")


def test_unresolved_ai_original_is_locked_not_promoted_to_human_evidence() -> None:
    raw = _response()
    result = preflight_mistral_reader_a(raw, source_use_authorized=True)
    assert result.original_response_sha256 == result.original_response_lock[
        "response_sha256"
    ]
    assert result.original_response_lock["status"] == (
        "RESPONSE_HASHED_NOT_HUMAN_ATTESTED"
    )
    assert result.original_response_lock["extraction_declared_complete"] is False
    assert result.metadata_schema_ready is False
    assert result.status == "PRIVATE_AI_FIRST_ROUND_NOT_HUMAN_VALIDATED"
    assert result.independent_human_extraction_received is False
    assert result.requirements_denominator_qualified is False
    assert result.G1_qualified is False
    assert result.confirmatory_permission is False
    assert verify_response_lock(raw, result.original_response_lock)[
        "extractor"
    ]["role"] == "AI_preliminary_extractor"


@pytest.mark.parametrize("authorization", [False, None, 0, 1, "yes"])
def test_source_use_must_be_explicit_actual_boolean(authorization) -> None:
    with pytest.raises(ValueError, match="source-use authorization"):
        preflight_mistral_reader_a(
            _response(), source_use_authorized=authorization
        )


@pytest.mark.parametrize("role", ["independent_LRI_required_element_extractor", "HUMAN", ""])
def test_cannot_label_mistral_first_round_as_human(role: str) -> None:
    d = yaml.safe_load(_response())
    d["extractor"]["role"] = role
    with pytest.raises(ValueError, match="AI Reader A"):
        preflight_mistral_reader_a(
            yaml.safe_dump(d).encode("utf-8"), source_use_authorized=True
        )


def test_missing_ai_provenance_cannot_be_passed_as_qualified_submission() -> None:
    d = yaml.safe_load(_response())
    d["extractor"]["prior_project_involvement"] = "None"
    d["notes"] = None
    with pytest.raises(ValueError, match="AI-assisted model provenance"):
        preflight_mistral_reader_a(
            yaml.safe_dump(d).encode("utf-8"), source_use_authorized=True
        )


def test_explicit_model_revision_required_for_normal_intake() -> None:
    d = yaml.safe_load(_response())
    d["notes"] = "Mistral AI-assisted; no pinned model revision"
    with pytest.raises(ValueError, match="model_id and model_version"):
        preflight_mistral_reader_a(
            yaml.safe_dump(d).encode("utf-8"), source_use_authorized=True
        )


@pytest.mark.parametrize(
    "revision", ["latest", "TBD", "unknown", "model-latest"]
)
def test_unpinned_or_placeholder_model_revision_rejected(revision: str) -> None:
    d = yaml.safe_load(_response())
    d["notes"] = (
        f"Mistral AI-assisted; model_id=mistral-synthetic-test; "
        f"model_version={revision}"
    )
    with pytest.raises(ValueError, match="model_id and model_version"):
        preflight_mistral_reader_a(
            yaml.safe_dump(d).encode("utf-8"), source_use_authorized=True
        )


def test_disclosed_exposure_is_byte_locked_but_scientifically_quarantined() -> None:
    d = yaml.safe_load(_response())
    d["independence"]["other_extractor_output_seen_before_completion"] = True
    raw = yaml.safe_dump(d, sort_keys=False).encode("utf-8")
    result = preflight_mistral_reader_a(raw, source_use_authorized=True)
    assert result.status == "PRIVATE_AI_EXPOSURE_QUARANTINED_NOT_ELIGIBLE"
    assert result.original_response_lock["status"] == (
        "AI_FIRST_ROUND_EXPOSURE_QUARANTINED"
    )
    assert result.original_response_sha256 == result.original_response_lock[
        "response_sha256"
    ]
    assert result.original_response_lock[
        "declared_exposure_or_missing_independence_flags"
    ] == ["other_extractor_output_seen_before_completion"]
    assert result.metadata_schema_ready is False
    assert result.independent_human_extraction_received is False
    assert result.G1_qualified is False
    with pytest.raises(ValueError, match="invalid extraction response lock version"):
        verify_response_lock(raw, result.original_response_lock)


def test_exposed_original_digest_changes_with_any_byte_change() -> None:
    d = yaml.safe_load(_response())
    d["independence"]["renderer_output_used_as_requirement_evidence"] = True
    raw = yaml.safe_dump(d, sort_keys=False).encode("utf-8")
    original = preflight_mistral_reader_a(raw, source_use_authorized=True)
    altered = preflight_mistral_reader_a(raw + b"\n", source_use_authorized=True)
    assert original.original_response_sha256 != altered.original_response_sha256
    assert original.status == altered.status


def test_response_tampering_after_initial_lock_rejected() -> None:
    raw = _response()
    captured = preflight_mistral_reader_a(raw, source_use_authorized=True)
    with pytest.raises(ValueError, match="original complete lock"):
        verify_response_lock(raw + b"\n# altered", captured.original_response_lock)


def test_public_blank_template_cannot_impersonate_mistral() -> None:
    with open(
        "qualification/hl7v2/required_element_review/examples/extraction_template.yaml",
        "rb",
    ) as source:
        raw = source.read()
    with pytest.raises(ValueError, match="placeholders|AI Reader A"):
        preflight_mistral_reader_a(raw, source_use_authorized=True)


def test_mistral_run_id_must_differ_from_reviewer_pseudonym() -> None:
    d = yaml.safe_load(_response())
    d["extraction_id"] = "MISTRAL-READER-A"
    with pytest.raises(ValueError, match="separate unique response"):
        preflight_mistral_reader_a(
            yaml.safe_dump(d).encode("utf-8"), source_use_authorized=True
        )


def test_syntactically_complete_ai_response_is_still_not_human_ground_truth() -> None:
    d = yaml.safe_load(_response())
    d["extraction_complete"] = True
    d["entries"][0].update({
        "usage": "R",
        "cardinality": "1..1",
        "source_grounding_classification": "SOURCE_FACT",
        "classification_rationale": "Synthetic only",
        "evidence": ["Synthetic fixture; not real Edition 5 source evidence"],
    })
    # Even self-declared complete-looking AI input cannot produce G1.
    result = preflight_mistral_reader_a(
        yaml.safe_dump(d, sort_keys=False).encode("utf-8"),
        source_use_authorized=True,
    )
    assert result.metadata_schema_ready
    assert result.G1_qualified is False
    assert result.independent_human_extraction_received is False
    assert result.requirements_denominator_qualified is False


def test_output_scientific_gate_properties_are_immutable() -> None:
    result = preflight_mistral_reader_a(
        _response(), source_use_authorized=True
    )
    with pytest.raises(FrozenInstanceError):
        result.G1_qualified = True
    with pytest.raises(FrozenInstanceError):
        result.confirmatory_permission = True



def _intake_cli():
    # The qualification folder is a repository script directory, not an
    # installed Python package. Import its CLI by file path from tests.
    script = (
        Path(__file__).resolve().parents[1]
        / "qualification/hl7v2/required_element_review/intake_mistral_reader_a.py"
    )
    return runpy.run_path(str(script))


def test_private_cli_original_lock_is_exclusive_and_never_overwritten(
    tmp_path, monkeypatch, capsys
) -> None:
    main = _intake_cli()["main"]

    source = tmp_path / "original.yaml"
    lock = tmp_path / "original.lock.json"
    original_bytes = _response()
    source.write_bytes(original_bytes)
    argv = [
        "intake_mistral_reader_a.py", str(source), str(lock),
        "--source-use-authorized",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 0
    receipt = json.loads(lock.read_text(encoding="utf-8"))
    assert receipt["status"] == "RESPONSE_HASHED_NOT_HUMAN_ATTESTED"
    assert verify_response_lock(original_bytes, receipt)["extractor"]["role"] == (
        "AI_preliminary_extractor"
    )
    if os.name == "posix":
        assert lock.stat().st_mode & 0o777 == 0o600
    output = capsys.readouterr().out
    assert "PRIVATE_AI_FIRST_ROUND_NOT_HUMAN_VALIDATED" in output
    assert "confirmatory_permission" in output
    assert "Synthetic fixture" not in output
    assert main() == 1
    assert json.loads(lock.read_text(encoding="utf-8")) == receipt
    assert "FAIL_CLOSED" in capsys.readouterr().out


def test_cli_immutably_quarantines_truthful_exposure(
    tmp_path, monkeypatch, capsys
) -> None:
    main = _intake_cli()["main"]
    doc = yaml.safe_load(_response())
    doc["independence"][
        "project_required_element_inventory_seen_before_completion"
    ] = True
    original = tmp_path / "mistral-exposed-original.yaml"
    raw = yaml.safe_dump(doc, sort_keys=False).encode("utf-8")
    original.write_bytes(raw)
    quarantine_path = tmp_path / "mistral-exposed.lock.json"
    monkeypatch.setattr(sys, "argv", [
        "intake_mistral_reader_a.py", str(original), str(quarantine_path),
        "--source-use-authorized",
    ])
    assert main() == 2
    receipt = json.loads(quarantine_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "AI_FIRST_ROUND_EXPOSURE_QUARANTINED"
    assert receipt["human_independent_extraction"] is False
    assert "PRIVATE_AI_EXPOSURE_QUARANTINED_NOT_ELIGIBLE" in capsys.readouterr().out
    assert original.read_bytes() == raw
    with pytest.raises(ValueError, match="invalid extraction response lock version"):
        verify_response_lock(raw, receipt)
    assert main() == 1
    assert json.loads(quarantine_path.read_text(encoding="utf-8")) == receipt


def test_cli_rejects_public_repository_paths_before_reading_private_evidence(
    tmp_path, monkeypatch, capsys
) -> None:
    source_module = _intake_cli()
    main = source_module["main"]
    _REPOSITORY_ROOT = source_module["_REPOSITORY_ROOT"]

    target = tmp_path / "private.lock.json"
    monkeypatch.setattr(sys, "argv", [
        "intake_mistral_reader_a.py",
        str(_REPOSITORY_ROOT / "README.md"),
        str(target),
        "--source-use-authorized",
    ])
    assert main() == 1
    assert not target.exists()
    assert "outside the public repository" in capsys.readouterr().out


def test_cli_requires_coordinator_authorization_flag(
    tmp_path, monkeypatch, capsys
) -> None:
    main = _intake_cli()["main"]

    source = tmp_path / "original.yaml"
    source.write_bytes(_response())
    lock = tmp_path / "original.lock.json"
    monkeypatch.setattr(
        sys, "argv", ["intake_mistral_reader_a.py", str(source), str(lock)]
    )
    assert main() == 1
    assert not lock.exists()
    assert "source-use authorization" in capsys.readouterr().out
