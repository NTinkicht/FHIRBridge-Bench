"""Development-only third-source v0.3 rule census with synthetic inputs."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_rule_level_extraction_v03 import create_v03_response_lock
from fhirbridge.path_b_v03_source_census import audit_v03_independent_source_census

_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/"
    "rule_level_extraction_v03_blank.yaml"
)
_CENSUS = Path(
    "qualification/hl7v2/required_element_review/examples/"
    "third_source_census_v03_blank.json"
)


def _rule(identifier: str, condition: str) -> dict:
    return {
        "candidate_rule_id": identifier,
        "rule_kind": "CONDITIONAL_PREDICATE",
        "locus": "OBR-3",
        "element_kind": "field",
        "usage": "C",
        "cardinality": "1..1",
        "datatype": "EI",
        "max_length": None,
        "condition": condition,
        "value_set_or_binding_ref": None,
        "source_grounding_classification": "SOURCE_FACT",
        "classification_rationale": "SYNTHETIC TEST ONLY",
        "evidence": ["synthetic test page 1; no actual HL7 source review"],
    }


def _reader(identity: str, *, second_rule: bool = True) -> tuple[bytes, dict]:
    doc = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    doc["extraction_id"] = "SYNTHETIC-V03-" + identity
    doc["extractor"]["extractor_id"] = identity
    doc["entries"] = [_rule(identity + "-A", "synthetic predicate A")]
    if second_rule:
        doc["entries"].append(_rule(identity + "-B", "synthetic predicate B"))
    doc["extraction_complete"] = True
    raw = yaml.safe_dump(doc, sort_keys=False).encode("utf-8")
    return raw, create_v03_response_lock(raw)


def _source_census() -> dict:
    doc = json.loads(_CENSUS.read_text(encoding="utf-8"))
    doc["census_reviewer_id"] = "SYNTHETIC-CENSUS-THIRD"
    area = next(x for x in doc["scope_areas"] if x["coverage_area"] == "OBR")
    area.update({"status": "SOURCE_PAGES_CHECKED", "source_pages": [101, 102]})
    doc["candidate_requirements"] = [
        {
            "coverage_area": "OBR",
            "source_pages": [101],
            "rule": _rule("CEN-THIRD-A", "synthetic predicate A"),
        },
        {
            "coverage_area": "OBR",
            "source_pages": [102],
            "rule": _rule("CEN-THIRD-C", "synthetic predicate C"),
        },
    ]
    return doc


def _audit(census=None, *, first=None, second=None):
    first = first or _reader("READER-A")
    second = second or _reader("READER-B")
    data = json.dumps(
        census if census is not None else _source_census()
    ).encode("utf-8")
    return audit_v03_independent_source_census(
        raw_a=first[0],
        lock_a=first[1],
        raw_b=second[0],
        lock_b=second[1],
        source_census_json_bytes=data,
    )


def test_same_field_census_rule_missing_from_both_is_not_hidden_by_locus() -> None:
    report = _audit()
    assert report.status == "PRIVATE_V03_RULE_LEVEL_CENSUS_TRIAGE_ONLY"
    assert report.candidate_rule_count == 2
    assert report.distinct_candidate_locus_count == 1
    assert report.rules_not_found_in_either_reader == ("CEN-THIRD-C",)
    assert report.same_locus_but_no_matching_rule == ("CEN-THIRD-C",)
    assert report.matching_candidate_rules_requiring_human_review == ("CEN-THIRD-A",)
    assert report.independently_established_requirements_denominator is None
    assert report.scientific_completeness_certified is False
    assert report.human_adjudication_performed is False
    assert report.reviewer_independence_verified_by_software is False
    assert report.G1_qualified is False
    assert report.confirmatory_permission is False
    assert "MSH" in report.unreviewed_scope_areas


def test_reader_specific_ids_do_not_influence_substantive_match() -> None:
    census = _source_census()
    census["candidate_requirements"][0]["rule"]["candidate_rule_id"] = (
        "ARBITRARY-DIFFERENT-CENSUS-ID"
    )
    result = _audit(census)
    assert result.matching_candidate_rules_requiring_human_review == (
        "ARBITRARY-DIFFERENT-CENSUS-ID",
    )


def test_candidate_missing_from_one_not_both_is_not_a_double_omission() -> None:
    census = _source_census()
    first = _reader("READER-A", second_rule=False)
    doc = yaml.safe_load(_reader("READER-B")[0])
    doc["entries"].append(_rule("READER-B-C", "synthetic predicate C"))
    raw = yaml.safe_dump(doc, sort_keys=False).encode("utf-8")
    second = (raw, create_v03_response_lock(raw))
    result = _audit(census, first=first, second=second)
    assert result.rules_not_found_in_either_reader == ()
    assert set(result.matching_candidate_rules_requiring_human_review) == {
        "CEN-THIRD-A", "CEN-THIRD-C",
    }


def test_no_candidates_or_complete_self_report_can_never_certify_denominator() -> None:
    census = _source_census()
    for row in census["scope_areas"]:
        row["status"] = "SOURCE_PAGES_CHECKED"
        row["source_pages"] = [1]
    census["candidate_requirements"] = []
    report = _audit(census)
    assert report.candidate_rule_count == 0
    assert report.unreviewed_scope_areas == ()
    assert report.independently_established_requirements_denominator is None
    assert report.G1_qualified is False


def test_same_rule_id_with_conflicting_predicate_not_silently_matched() -> None:
    census = _source_census()
    census["candidate_requirements"][0]["rule"]["candidate_rule_id"] = "READER-A-A"
    census["candidate_requirements"][0]["rule"]["condition"] = "other condition"
    report = _audit(census)
    assert "READER-A-A" in report.same_locus_but_no_matching_rule


def test_census_exact_input_bytes_are_hashed_separately() -> None:
    original = _source_census()
    first = _audit(original)
    modified = deepcopy(original)
    modified["candidate_requirements"][1]["source_pages"] = [101, 102]
    second = _audit(modified)
    assert first.third_source_census_sha256 != second.third_source_census_sha256
    assert first.first_reader_sha256 == second.first_reader_sha256
    assert len(first.third_source_census_sha256) == len(sha256(b"test").hexdigest())


@pytest.mark.parametrize("alter", [
    "unsupported-version", "fake-scientific-claim", "unapproved-source",
    "wrong-reviewer", "duplicate-rule-id", "duplicate-rule-content",
    "missing-predicate", "unreviewed-area", "missing-page", "fake-page",
    "blank-evidence", "missing-binding",
])
def test_third_source_census_fails_closed_on_invalid_claims(alter: str) -> None:
    census = _source_census()
    row = census["candidate_requirements"][0]
    if alter == "unsupported-version":
        census["schema_version"] = "0.2.0"
    elif alter == "fake-scientific-claim":
        census["G1_qualified"] = True
    elif alter == "unapproved-source":
        census["errata_sha256"] = "0" * 64
    elif alter == "wrong-reviewer":
        census["census_reviewer_id"] = "READER-A"
    elif alter == "duplicate-rule-id":
        census["candidate_requirements"][1]["rule"]["candidate_rule_id"] = (
            row["rule"]["candidate_rule_id"]
        )
    elif alter == "duplicate-rule-content":
        replica = deepcopy(row)
        replica["rule"]["candidate_rule_id"] = "CEN-THIRD-REPLICA"
        census["candidate_requirements"].append(replica)
    elif alter == "missing-predicate":
        row["rule"]["condition"] = "TO_BE_DECIDED"
    elif alter == "unreviewed-area":
        row["coverage_area"] = "PID"
    elif alter == "missing-page":
        row["source_pages"] = []
    elif alter == "fake-page":
        row["source_pages"] = [True]
    elif alter == "blank-evidence":
        row["rule"]["evidence"] = ["TO_BE_SOURCE_CITED"]
    elif alter == "missing-binding":
        row["rule"]["rule_kind"] = "VALUE_SET_BINDING"
        row["rule"]["value_set_or_binding_ref"] = None
    with pytest.raises(ValueError):
        _audit(census)


def test_v02_original_lock_cannot_be_passed_as_a_v03_source() -> None:
    from fhirbridge.lri_extraction_lock import create_response_lock

    original = Path(
        "qualification/hl7v2/required_element_review/examples/extraction_template.yaml"
    ).read_bytes()
    legacy = create_response_lock(original)
    with pytest.raises(ValueError, match="invalid v0.3 lock version"):
        _audit(first=(original, legacy))


def test_scientific_flags_cannot_be_set_by_programmatic_mutation() -> None:
    report = _audit()
    with pytest.raises(FrozenInstanceError):
        report.G1_qualified = True
    with pytest.raises(FrozenInstanceError):
        report.confirmatory_permission = True
