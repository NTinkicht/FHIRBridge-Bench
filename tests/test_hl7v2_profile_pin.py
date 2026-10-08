from copy import deepcopy

import pytest
import yaml

from fhirbridge.hl7v2_profile_pin import (
    assert_hl7_profile_pin_frozen,
    assess_hl7_profile_pin,
)

_PROFILE_PIN = "benchmark/hl7v2_lri_profile_pin.yaml"


def _document() -> dict:
    with open(_PROFILE_PIN, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _set_path(document: dict, dotted_path: str, value) -> None:
    current = document
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def test_candidate_lri_profile_pin_is_not_freeze_ready() -> None:
    readiness = assess_hl7_profile_pin(_document())

    assert readiness.status == "candidate"
    assert not readiness.ready
    assert "acquisition.igamt_export_identifier" in readiness.unresolved_paths
    assert "bundle.aggregate_sha256" in readiness.unresolved_paths
    assert (
        "identity_verification.independent_profile_provenance_reviewed"
        in readiness.false_boolean_paths
    )
    assert readiness.exact_value_mismatches == ()


@pytest.mark.parametrize(
    ("path", "wrong_value"),
    (
        ("target.hl7_version", "2.3.1"),
        ("target.message_type", "ADT"),
        ("target.event_type", "A01"),
        ("target.message_structure", "ADT_A01"),
        ("target.implementation_guide_edition", "2016"),
        ("target.errata", "2016"),
    ),
)
def test_wrong_or_stale_profile_identity_blocks_freeze(
    path: str,
    wrong_value: str,
) -> None:
    document = _document()
    _set_path(document, path, wrong_value)

    readiness = assess_hl7_profile_pin(document)

    assert not readiness.ready
    assert path in readiness.exact_value_mismatches


def test_profile_pin_cannot_claim_frozen_while_unresolved() -> None:
    document = _document()
    document["profile_pin"]["status"] = "frozen"

    with pytest.raises(ValueError, match="cannot be marked frozen"):
        assess_hl7_profile_pin(document)


def test_fully_qualified_profile_pin_can_be_frozen() -> None:
    document = deepcopy(_document())
    gate = document["freeze_gate"]

    for path in gate["required_resolved_paths"]:
        _set_path(document, path, f"resolved:{path}")
    for path in gate["required_true_paths"]:
        _set_path(document, path, True)
    document["profile_pin"]["status"] = "frozen"

    readiness = assess_hl7_profile_pin(document)

    assert readiness.ready
    assert readiness.unresolved_paths == ()
    assert readiness.false_boolean_paths == ()
    assert readiness.exact_value_mismatches == ()
    assert_hl7_profile_pin_frozen(document)


def test_complete_but_unfrozen_profile_pin_is_rejected_for_confirmatory_use() -> None:
    document = deepcopy(_document())
    gate = document["freeze_gate"]

    for path in gate["required_resolved_paths"]:
        _set_path(document, path, f"resolved:{path}")
    for path in gate["required_true_paths"]:
        _set_path(document, path, True)

    with pytest.raises(ValueError, match="status must be frozen"):
        assert_hl7_profile_pin_frozen(document)
