"""Synthetic v0.3 rule-level review: never official HL7 conformance."""

from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest
import yaml

from fhirbridge.lri_extraction_lock import (
    create_response_lock,
    verify_response_lock,
)
from fhirbridge.lri_rule_level_extraction_v03 import (
    assess_rule_level_v03,
    create_v03_response_lock,
    triage_locked_v03_extractions,
    verify_v03_response_lock,
)

_BASE = (
    "qualification/hl7v2/required_element_review/examples/"
    "rule_level_extraction_v03_blank.yaml"
)
_LEGACY = (
    "qualification/hl7v2/required_element_review/examples/"
    "extraction_template.yaml"
)


def _rule(
    rid: str,
    *,
    kind: str = "USAGE",
    usage: str = "R",
    condition=None,
    binding=None,
    locus: str = "OBR-3",
) -> dict:
    return {
        "candidate_rule_id": rid,
        "rule_kind": kind,
        "locus": locus,
        "element_kind": "field",
        "usage": usage,
        "cardinality": "1..1",
        "datatype": "EI",
        "max_length": None,
        "condition": condition,
        "value_set_or_binding_ref": binding,
        "source_grounding_classification": "SOURCE_FACT",
        "classification_rationale": "SYNTHETIC test claim, no real HL7 truth",
        "evidence": ["SYNTHETIC-EVIDENCE p.1, not an actual standard"],
    }


def _extract(identity: str, rules=None) -> dict:
    with open(_BASE, encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    document["extraction_id"] = f"SYNTHETIC-V03-{identity}"
    document["extractor"]["extractor_id"] = identity
    document["extractor"]["prior_project_involvement"] = "Synthetic tests only"
    document["extractor"]["conflicts_of_interest"] = "Synthetic tests only"
    document["entries"] = rules if rules is not None else [
        _rule(f"{identity}-USAGE"),
        _rule(
            f"{identity}-IF-A",
            kind="CONDITIONAL_PREDICATE",
            usage="C",
            condition="SYNTHETIC condition A",
        ),
        _rule(
            f"{identity}-IF-B",
            kind="CONDITIONAL_PREDICATE",
            usage="C",
            condition="SYNTHETIC condition B",
        ),
    ]
    document["extraction_complete"] = True
    return document


def _raw(doc: dict) -> bytes:
    return yaml.safe_dump(doc, sort_keys=False).encode("utf-8")


def _compare(a=None, b=None):
    left = _raw(a if a is not None else _extract("SYN-A"))
    right = _raw(b if b is not None else _extract("SYN-B"))
    return triage_locked_v03_extractions(
        left, create_v03_response_lock(left),
        right, create_v03_response_lock(right),
    )


def test_same_locus_can_have_three_separate_rule_candidates() -> None:
    a = _extract("SYN-A")
    assert [r["locus"] for r in a["entries"]] == ["OBR-3"] * 3
    assert assess_rule_level_v03(a) == ()
    report = _compare()
    assert report.candidate_counts == (3, 3)
    assert len(report.mechanically_identical_content_pairs) == 3
    assert report.reader_a_only_candidates == ()
    assert report.reader_b_only_candidates == ()
    assert report.per_locus_candidate_counts == ({
        "locus": "OBR-3",
        "reader_a_count": 3,
        "reader_b_count": 3,
        "identical_content_pairs": 3,
        "human_completeness_audit_required": True,
    },)
    for entry in report.mechanically_identical_content_pairs:
        assert entry["reader_a_rule_id"] != entry["reader_b_rule_id"]
        assert entry["human_source_audit_required"] is True
    assert report.independently_established_requirements_denominator is None
    assert report.human_adjudication_performed is False
    assert report.scientific_completeness_certified is False
    assert report.G1_qualified is False
    assert report.confirmatory_permission is False


def test_one_reader_omits_second_conditional_predicate_same_field() -> None:
    a, b = _extract("SYN-A"), _extract("SYN-B")
    b["entries"].pop()
    report = _compare(a, b)
    assert len(report.mechanically_identical_content_pairs) == 2
    assert len(report.reader_a_only_candidates) == 1
    assert report.reader_a_only_candidates[0]["entry"]["condition"] == (
        "SYNTHETIC condition B"
    )
    assert report.reader_a_only_candidates[0]["same_locus_exists_in_other_reader"] is True
    assert report.per_locus_candidate_counts[0]["reader_a_count"] == 3
    assert report.per_locus_candidate_counts[0]["reader_b_count"] == 2
    assert report.scientific_completeness_certified is False


def test_same_physical_field_but_different_binding_not_auto_matched() -> None:
    a, b = _extract("SYN-A"), _extract("SYN-B")
    b["entries"][0]["value_set_or_binding_ref"] = "SYNTHETIC-VALUESET-B"
    report = _compare(a, b)
    assert len(report.mechanically_identical_content_pairs) == 2
    assert len(report.reader_a_only_candidates) == 1
    assert len(report.reader_b_only_candidates) == 1
    assert report.reader_b_only_candidates[0]["same_locus_exists_in_other_reader"]


def test_different_candidate_ids_never_block_exact_content_comparison() -> None:
    a, b = _extract("SYN-A"), _extract("SYN-B")
    for i, row in enumerate(b["entries"]):
        row["candidate_rule_id"] = "COMPLETELY-DIFFERENT-ID-" + str(i)
    assert len(_compare(a, b).mechanically_identical_content_pairs) == 3


def test_same_id_across_readers_does_not_force_equivalence() -> None:
    a, b = _extract("SYN-A"), _extract("SYN-B")
    b["entries"][1]["candidate_rule_id"] = a["entries"][1]["candidate_rule_id"]
    b["entries"][1]["condition"] = "SYNTHETIC DIFFERENT PREDICATE"
    report = _compare(a, b)
    assert len(report.mechanically_identical_content_pairs) == 2
    assert len(report.reader_a_only_candidates) == 1
    assert len(report.reader_b_only_candidates) == 1


def test_different_source_citation_kept_for_human_review() -> None:
    a, b = _extract("SYN-A"), _extract("SYN-B")
    b["entries"][2]["evidence"] = ["SYNTHETIC DIFFERENT SOURCE PAGE"]
    report = _compare(a, b)
    assert len(report.mechanically_identical_content_pairs) == 3
    assert len(report.citation_or_rationale_differences) == 1
    assert report.citation_or_rationale_differences[0]["human_source_audit_required"]


def test_R_and_independent_DATATYPE_at_one_field_both_retained() -> None:
    a = _extract("SYN-A")
    a["entries"].append(_rule("SYN-A-DATATYPE", kind="DATATYPE"))
    b = _extract("SYN-B")
    b["entries"].append(_rule("SYN-B-DATATYPE", kind="DATATYPE"))
    report = _compare(a, b)
    assert len(report.mechanically_identical_content_pairs) == 4


def test_duplicate_rule_id_or_duplicate_semantic_rule_cannot_inflate_denominator() -> None:
    a = _extract("SYN-A")
    a["entries"][1]["candidate_rule_id"] = a["entries"][0]["candidate_rule_id"]
    with pytest.raises(ValueError, match="duplicate candidate rule ID"):
        create_v03_response_lock(_raw(a))
    a = _extract("SYN-A")
    duplicate = deepcopy(a["entries"][1])
    duplicate["candidate_rule_id"] = "OTHER-RULE-ID"
    a["entries"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate substantive candidate"):
        create_v03_response_lock(_raw(a))


@pytest.mark.parametrize("condition", [None, "", "TO_BE_DECIDED"])
def test_conditional_predicate_never_becomes_ready_if_missing(condition) -> None:
    a = _extract("SYN-A")
    a["entries"][1]["condition"] = condition
    blockers = assess_rule_level_v03(a)
    assert any("conditional predicate missing" in issue for issue in blockers)
    if condition in (None, ""):
        with pytest.raises(ValueError, match="schema error"):
            create_v03_response_lock(_raw(a))
    else:
        # Preserve a syntactically valid but unresolved original response.
        # Its immutable lock explicitly records the missing scientific fact.
        lock = create_v03_response_lock(_raw(a))
        assert lock["metadata_ready"] is False
        assert lock["qualified_G1"] is False


def test_unresolved_entry_can_be_captured_but_never_certified() -> None:
    a = _extract("SYN-A")
    a["entries"][0]["usage"] = "UNKNOWN"
    a["entries"][0]["source_grounding_classification"] = "UNRESOLVED"
    a["extraction_complete"] = False
    raw = _raw(a)
    lock = create_v03_response_lock(raw)
    assert lock["metadata_ready"] is False
    assert lock["qualified_G1"] is False
    assert "not self-declared complete" in " ".join(lock["readiness_blockers"])
    assert verify_v03_response_lock(raw, lock)["entries"][0]["usage"] == "UNKNOWN"


def test_v03_source_pins_always_required() -> None:
    a = _extract("SYN-A")
    a["source"]["artifact_sha256"] = "1" * 64
    with pytest.raises(ValueError, match="source hashes"):
        create_v03_response_lock(_raw(a))


def test_first_round_lock_fails_on_any_byte_mutation() -> None:
    raw = _raw(_extract("SYN-A"))
    lock = create_v03_response_lock(raw)
    with pytest.raises(ValueError, match="bytes or lock metadata changed"):
        verify_v03_response_lock(raw + b"\n# changed", lock)
    with pytest.raises(ValueError, match="invalid v0.3 lock version"):
        verify_v03_response_lock(raw, lock | {"lock_schema_version": "0.2.0"})
    forged = deepcopy(lock)
    forged["qualified_G1"] = 0
    with pytest.raises(ValueError, match="bytes or lock metadata changed"):
        verify_v03_response_lock(raw, forged)


def test_original_legacy_v02_lock_is_byte_identical_compatible() -> None:
    with open(_LEGACY, encoding="utf-8") as stream:
        old = yaml.safe_load(stream)
    old["extraction_id"] = "SYNTHETIC-LEGACY-LOCK"
    old["extractor"]["extractor_id"] = "LEGACY-SYN-A"
    oldraw = _raw(old)
    legacy = create_response_lock(oldraw)
    assert verify_response_lock(oldraw, legacy)["schema_version"] == "0.2.0"
    assert legacy["lock_schema_version"] == "0.1.0"
    with pytest.raises(ValueError, match="invalid v0.3 lock version"):
        verify_v03_response_lock(oldraw, legacy)


def test_noncanonical_field_locus_fails_schema() -> None:
    for wrong in ("OBR-3#C2", "OBR-3.0-extra", "OBR-3 ", "OBR-3|CONDITION"):
        a = _extract("SYN-A")
        a["entries"][1]["locus"] = wrong
        with pytest.raises(ValueError, match="schema error"):
            create_v03_response_lock(_raw(a))


def test_input_claims_cannot_issue_scientific_qualification() -> None:
    a = _extract("SYN-A")
    a["independently_established_requirements_denominator"] = 999
    with pytest.raises(ValueError, match="schema error"):
        create_v03_response_lock(_raw(a))


def test_independence_flag_true_fails_review_intake() -> None:
    a = _extract("SYN-A")
    a["independence"]["other_extractor_output_seen_before_completion"] = True
    with pytest.raises(ValueError, match="isolation conditions|schema error"):
        create_v03_response_lock(_raw(a))


def test_output_status_cannot_be_mutated_into_scientific_approval() -> None:
    result = _compare()
    with pytest.raises(FrozenInstanceError):
        result.G1_qualified = True
