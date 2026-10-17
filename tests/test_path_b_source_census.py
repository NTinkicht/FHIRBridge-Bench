"""Source census is an independent *candidate*, never a verified denominator."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_extraction_lock import create_response_lock
from fhirbridge.lri_source_identity import pinned_publication_hashes
from fhirbridge.path_b_source_census import (
    _CENSUS_AREAS,
    audit_candidate_source_census,
)

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
        "classification_rationale": f"Synthetic test only for {locus}",
        "evidence": [f"TEST ONLY {locus} page 1"],
    }


def _locked_reviewer(identity: str) -> tuple[bytes, dict]:
    doc = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    doc["extraction_id"] = f"SYNTHETIC-{identity}"
    doc["extractor"]["extractor_id"] = identity
    doc["extraction_complete"] = True
    doc["entries"] = [_entry("ORC-3"), _entry("OBR-3")]
    raw = yaml.safe_dump(doc, sort_keys=False).encode("utf-8")
    return raw, create_response_lock(raw)


def _census() -> dict:
    pins = pinned_publication_hashes()
    return {
        "schema_version": "0.1.0",
        "status": "UNADJUDICATED_SOURCE_CENSUS_DRAFT",
        "census_reviewer_id": "SYNTHETIC-THIRD",
        "source_sha256": pins["implementation_guide"],
        "errata_sha256": pins["errata_letter"],
        "scope_areas": [
            {
                "coverage_area": area,
                "status": "SOURCE_PAGES_CHECKED" if area in ("MSH", "ORC", "OBR") else "UNREVIEWED",
                "source_pages": [1] if area in ("MSH", "ORC", "OBR") else [],
            }
            for area in _CENSUS_AREAS
        ],
        "candidate_requirements": [
            {
                "census_rule_id": "CEN-MSH21",
                "locus": "MSH-21",
                "usage": "R",
                "condition": None,
                "coverage_area": "MSH",
                "source_pages": [152],
            },
            {
                "census_rule_id": "CEN-ORC3",
                "locus": "ORC-3",
                "usage": "R",
                "condition": None,
                "coverage_area": "ORC",
                "source_pages": [185],
            },
            {
                "census_rule_id": "CEN-OBR3-IF",
                "locus": "OBR-3",
                "usage": "C",
                "condition": "SYNTHETIC ONLY: illustrative predicate",
                "coverage_area": "OBR",
                "source_pages": [186],
            },
        ],
    }


def _audit(
    census: dict,
    *,
    first: tuple[bytes, dict] | None = None,
    second: tuple[bytes, dict] | None = None,
):
    first = first or _locked_reviewer("SYNTHETIC-A")
    second = second or _locked_reviewer("SYNTHETIC-B")
    return audit_candidate_source_census(
        raw_a=first[0],
        lock_a=first[1],
        raw_b=second[0],
        lock_b=second[1],
        census_bytes=json.dumps(census).encode("utf-8"),
    )


def test_third_source_finds_double_omission_but_not_equivalence_by_locus() -> None:
    report = _audit(_census())
    assert report.status == "PRIVATE_SOURCE_CENSUS_CANDIDATE_TRIAGE_ONLY"
    assert report.census_candidate_rule_count == 3
    assert report.observed_first_two_reader_locus_count == 2
    assert report.candidate_rule_ids_missing_from_both == ("CEN-MSH21",)
    assert report.candidate_loci_missing_from_both == ("MSH-21",)
    assert report.same_locus_rule_ids_requiring_source_comparison == (
        "CEN-OBR3-IF", "CEN-ORC3",
    )
    assert "PID" in report.unreviewed_source_areas
    assert report.independently_established_requirements_denominator is None
    assert report.standards_completeness_certified is False
    assert report.human_adjudication_performed is False
    assert report.reviewer_independence_verified_by_software is False
    assert report.G1_qualified is False
    assert report.confirmatory_permission is False
    assert report.source_census_sha256 == sha256(
        json.dumps(_census()).encode("utf-8")
    ).hexdigest()
    assert report.original_response_sha256 == (
        sha256(_locked_reviewer("SYNTHETIC-A")[0]).hexdigest(),
        sha256(_locked_reviewer("SYNTHETIC-B")[0]).hexdigest(),
    )


def test_duplicate_requirements_same_locus_do_not_silently_collapse() -> None:
    census = _census()
    second = deepcopy(census["candidate_requirements"][0])
    second["census_rule_id"] = "CEN-MSH21-OTHER-CONDITION"
    second["usage"] = "C"
    second["condition"] = "SYNTHETIC alternative predicate"
    census["candidate_requirements"].append(second)
    report = _audit(census)
    assert report.census_candidate_rule_count == 4
    assert report.candidate_rule_ids_missing_from_both == (
        "CEN-MSH21", "CEN-MSH21-OTHER-CONDITION",
    )
    assert report.candidate_loci_missing_from_both == ("MSH-21",)
    assert report.independently_established_requirements_denominator is None


def test_third_census_does_not_use_the_first_two_readers_as_denominator() -> None:
    census = _census()
    census["candidate_requirements"] = []
    report = _audit(census)
    assert report.census_candidate_rule_count == 0
    assert report.observed_first_two_reader_locus_count == 2
    assert report.independently_established_requirements_denominator is None
    assert report.G1_qualified is False


@pytest.mark.parametrize("id", ["SYNTHETIC-A", "SYNTHETIC-B", "", "TBD", "TO_BE_ASSIGNED"])
def test_third_census_identity_must_be_distinct_but_not_claim_verified(id: str) -> None:
    census = _census()
    census["census_reviewer_id"] = id
    with pytest.raises(ValueError, match="independent reviewer identity"):
        _audit(census)


@pytest.mark.parametrize("field", ["source_sha256", "errata_sha256"])
def test_census_source_pins_must_match_locked_originals(field: str) -> None:
    census = _census()
    census[field] = "0" * 64
    with pytest.raises(ValueError, match="pinned guide and errata"):
        _audit(census)


def test_tampered_original_response_lock_cannot_ground_census() -> None:
    first = _locked_reviewer("SYNTHETIC-A")
    with pytest.raises(ValueError, match="original complete lock"):
        _audit(_census(), first=(first[0] + b"\n# tampered", first[1]))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", "1.0.0"),
        ("status", "QUALIFIED"),
        ("census_reviewer_id", "SYNTHETIC-A"),
    ],
)
def test_metadata_forgery_rejected(key: str, value: str) -> None:
    census = _census()
    census[key] = value
    with pytest.raises(ValueError, match="status or independent reviewer identity"):
        _audit(census)


def test_unrequested_qualification_field_rejected() -> None:
    census = _census()
    census["G1_qualified"] = True
    with pytest.raises(ValueError, match="unsupported keys"):
        _audit(census)


def test_missing_or_duplicate_scope_area_never_certifies_completeness() -> None:
    census = _census()
    census["scope_areas"][-1] = deepcopy(census["scope_areas"][0])
    with pytest.raises(ValueError, match="duplicate, invalid or unsupported"):
        _audit(census)
    census = _census()
    census["scope_areas"].pop()
    with pytest.raises(ValueError, match="enumerate every bounded scope"):
        _audit(census)


def test_unreviewed_scope_area_cannot_claim_source_pages_or_rules() -> None:
    census = _census()
    next(a for a in census["scope_areas"] if a["coverage_area"] == "PID")[
        "source_pages"
    ] = [1]
    with pytest.raises(ValueError, match="coverage item is duplicate"):
        _audit(census)
    census = _census()
    census["candidate_requirements"][0]["coverage_area"] = "PID"
    with pytest.raises(ValueError, match="candidate source requirement"):
        _audit(census)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("census_rule_id", "CEN-WRONG_ID"),
        ("locus", ""),
        ("usage", "O"),
        ("coverage_area", "UNSUPPORTED"),
        ("source_pages", [True]),
        ("source_pages", [1, 1]),
    ],
)
def test_invalid_candidates_fail_closed(key: str, value: object) -> None:
    census = _census()
    census["candidate_requirements"][0][key] = value
    with pytest.raises(ValueError, match="candidate source requirement"):
        _audit(census)


def test_duplicate_census_rule_ids_are_rejected() -> None:
    census = _census()
    census["candidate_requirements"].append(deepcopy(census["candidate_requirements"][0]))
    with pytest.raises(ValueError, match="candidate source requirement"):
        _audit(census)


@pytest.mark.parametrize(
    ("usage", "condition"),
    [("C", None), ("C", ""), ("R", "SYNTHETIC"), ("X", None)],
)
def test_required_and_conditional_usage_constraints(usage: str, condition: str | None) -> None:
    census = _census()
    census["candidate_requirements"][0]["usage"] = usage
    census["candidate_requirements"][0]["condition"] = condition
    with pytest.raises(ValueError, match="candidate source requirement"):
        _audit(census)


@pytest.mark.parametrize(
    "prop", [
        "G1_qualified",
        "confirmatory_permission",
        "standards_completeness_certified",
        "human_adjudication_performed",
        "reviewer_independence_verified_by_software",
        "independently_established_requirements_denominator",
        "status",
    ],
)
def test_software_cannot_replace_properties_with_fake_sci_approval(prop: str) -> None:
    report = _audit(_census())
    with pytest.raises(TypeError):
        replace(report, **{prop: True})
    with pytest.raises(FrozenInstanceError):
        setattr(report, prop, True)


def test_source_census_json_with_drafts_stays_private_and_has_no_verdict() -> None:
    census = _census()
    report = _audit(json.loads(json.dumps(census)))
    assert report.status.endswith("TRIAGE_ONLY")
    assert report.G1_qualified is False
