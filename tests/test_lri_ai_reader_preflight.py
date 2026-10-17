"""Private Mistral Reader A intake: no authentic reviewer data in tests."""

import json
import os
import sys
from dataclasses import FrozenInstanceError

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
    doc["notes"] = "Mistral AI-assisted, unreviewed and not human-attested"
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
    with pytest.raises(ValueError, match="TO_BE_|AI Reader A"):
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



def test_private_cli_original_lock_is_exclusive_and_never_overwritten(
    tmp_path, monkeypatch, capsys
) -> None:
    from qualification.hl7v2.required_element_review.intake_mistral_reader_a import main

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


def test_cli_rejects_public_repository_paths_before_reading_private_evidence(
    tmp_path, monkeypatch, capsys
) -> None:
    from qualification.hl7v2.required_element_review.intake_mistral_reader_a import (
        _REPOSITORY_ROOT,
        main,
    )

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
    from qualification.hl7v2.required_element_review.intake_mistral_reader_a import main

    source = tmp_path / "original.yaml"
    source.write_bytes(_response())
    lock = tmp_path / "original.lock.json"
    monkeypatch.setattr(
        sys, "argv", ["intake_mistral_reader_a.py", str(source), str(lock)]
    )
    assert main() == 1
    assert not lock.exists()
    assert "source-use authorization" in capsys.readouterr().out
