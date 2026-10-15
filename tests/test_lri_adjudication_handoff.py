"""Adjudication preparation must not imply completeness or expert sign-off."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_adjudication_handoff import build_adjudication_handoff
from fhirbridge.lri_extraction_lock import create_response_lock

_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/extraction_template.yaml"
)


def _entry(locus: str) -> dict:
    return {
        "locus": locus,
        "element_kind": "field",
        "usage": "R",
        "cardinality": "1..1",
        "datatype": "EI",
        "max_length": None,
        "condition": None,
        "value_set_or_binding_ref": None,
        "source_grounding_classification": "SOURCE_FACT",
        "classification_rationale": f"Synthetic reason for {locus}",
        "evidence": [f"TEST ONLY / {locus}"],
    }


def _doc(reviewer: str) -> dict:
    doc = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    doc["extraction_id"] = f"EXT-{reviewer}"
    doc["extractor"]["extractor_id"] = reviewer
    doc["entries"] = [_entry("ORC-3"), _entry("OBR-3")]
    doc["extraction_complete"] = True
    return doc


def _raw(doc: dict) -> bytes:
    return yaml.safe_dump(doc, sort_keys=False).encode("utf-8")


def _packet(left: dict, right: dict) -> dict:
    a, b = _raw(left), _raw(right)
    return build_adjudication_handoff(
        a, create_response_lock(a), b, create_response_lock(b)
    )


def test_all_agreements_still_require_human_audit_and_scope_completeness() -> None:
    packet = _packet(_doc("R-A"), _doc("R-B"))
    assert packet["status"] == "PRIVATE_PRE_ADJUDICATION_REVIEW_REQUIRED"
    assert packet["observed_union_counts"] == {
        "total": 2,
        "one_reader_only": 0,
        "field_disagreements": 0,
        "observed_agreements": 2,
    }
    assert packet["observed_field_agreement_rate"] == 1.0
    assert packet["agreement_audit_plan"]["mode"] == "ALL_OBSERVED_AGREEMENTS"
    assert all(
        row["review_category"] == "OBSERVED_AGREEMENT_NEEDS_EVIDENCE_AUDIT"
        and row["human_disposition"] is None
        for row in packet["adjudication_rows"]
    )
    assert {row["coverage_area"] for row in packet["independent_scope_completeness_audit"]} >= {
        "MSH", "PID", "ORC", "OBR", "OBX", "SPM", "NTE_IF_PRESENT",
        "ADDITIONAL_APPLICABLE_LOCI_NOT_IN_EITHER_EXTRACTION",
    }
    assert packet["independently_established_requirements_denominator"] is None
    assert packet["omissions_in_both_extractions_checked"] is False
    assert packet["G1_qualified"] is False
    assert packet["confirmatory_permission"] is False
    assert packet["human_adjudication_performed"] is False
    assert packet["standards_completeness_certified"] is False


def test_missing_from_one_reader_routes_to_human_adjudication() -> None:
    a, b = _doc("R-A"), _doc("R-B")
    b["entries"] = [b["entries"][0]]
    packet = _packet(a, b)
    assert packet["observed_union_counts"]["one_reader_only"] == 1
    missing = next(x for x in packet["adjudication_rows"] if x["locus"] == "OBR-3")
    assert missing["review_category"] == "ONE_READER_ONLY"
    assert missing["reader_b_entry"] is None
    assert missing["reader_a_entry"]["usage"] == "R"
    assert missing["human_disposition"] is None


def test_attribute_disagreements_preserve_both_original_readings() -> None:
    a, b = _doc("R-A"), _doc("R-B")
    b["entries"][0]["usage"] = "RE"
    packet = _packet(a, b)
    assert packet["observed_union_counts"]["field_disagreements"] == 1
    row = next(x for x in packet["adjudication_rows"] if x["locus"] == "ORC-3")
    assert row["review_category"] == "FIELD_DISAGREEMENT"
    assert row["reader_a_entry"]["usage"] == "R"
    assert row["reader_b_entry"]["usage"] == "RE"


def test_matching_fields_but_different_evidence_require_an_audit() -> None:
    a, b = _doc("R-A"), _doc("R-B")
    b["entries"][0]["evidence"] = ["TEST ONLY / alternative page"]
    b["entries"][0]["classification_rationale"] = "Alternative source-grounding explanation"
    packet = _packet(a, b)
    row = next(x for x in packet["adjudication_rows"] if x["locus"] == "ORC-3")
    assert row["review_category"] == "OBSERVED_AGREEMENT_NEEDS_EVIDENCE_AUDIT"
    assert row["citation_or_rationale_differs"] is True
    assert row["reader_a_entry"]["evidence"] != row["reader_b_entry"]["evidence"]
    assert packet["observed_field_agreement_rate"] == 1.0
    assert packet["G1_qualified"] is False


def test_tampering_with_original_or_lock_fails_closed() -> None:
    a, b = _raw(_doc("R-A")), _raw(_doc("R-B"))
    lock_a, lock_b = create_response_lock(a), create_response_lock(b)
    with pytest.raises(ValueError, match="original complete lock record"):
        build_adjudication_handoff(
            a + b"\n# modified", lock_a, b, lock_b
        )
    bad_lock = deepcopy(lock_b)
    bad_lock["adjudication_performed"] = True
    with pytest.raises(ValueError, match="original complete lock record"):
        build_adjudication_handoff(a, lock_a, b, bad_lock)


def test_incomplete_locked_extraction_is_flagged_for_triage_not_qualified() -> None:
    a, b = _raw(_doc("R-A")), _doc("R-B")
    b["extraction_complete"] = False
    b["entries"][0]["usage"] = "UNKNOWN"
    b["entries"][0]["source_grounding_classification"] = "UNRESOLVED"
    raw_b = _raw(b)
    report = build_adjudication_handoff(
        a, create_response_lock(a), raw_b, create_response_lock(raw_b)
    )
    assert report["status"] == "PRIVATE_INCOMPLETE_EXTRACTION_TRIAGE_ONLY"
    assert report["original_metadata_readiness"]["reader_b_ready"] is False
    assert report["original_metadata_readiness"]["reader_b_blockers"]
    row = next(x for x in report["adjudication_rows"] if x["locus"] == "ORC-3")
    assert row["unknown_or_unresolved_initial_claim"] is True
    assert report["human_adjudication_performed"] is False
    assert report["G1_qualified"] is False


def test_disallowed_profile_does_not_enter_triage_even_if_locked() -> None:
    a, b = _doc("R-A"), _doc("R-B")
    b["source"]["profile_name"] = "UNVERIFIED"
    raw_a, raw_b = _raw(a), _raw(b)
    with pytest.raises(ValueError, match="incompatible source/profile"):
        build_adjudication_handoff(
            raw_a, create_response_lock(raw_a),
            raw_b, create_response_lock(raw_b),
        )


def test_same_reviewer_id_is_not_independent() -> None:
    raw = _raw(_doc("R-A"))
    lock = create_response_lock(raw)
    with pytest.raises(ValueError, match="different identifiers"):
        build_adjudication_handoff(raw, lock, raw, lock)
