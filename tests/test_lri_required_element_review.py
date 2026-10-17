from copy import deepcopy

import pytest
import yaml

from fhirbridge.lri_required_element_review import (
    assess_required_element_extraction,
    compare_required_element_extractions,
    extraction_comparison_to_dict,
)

_TEMPLATE = (
    "qualification/hl7v2/required_element_review/examples/"
    "extraction_template.yaml"
)


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _complete(extractor_id: str) -> dict:
    document = _template()
    document["extraction_id"] = f"EXT-{extractor_id}"
    document["extractor"]["extractor_id"] = extractor_id
    document["extractor"]["conflicts_of_interest"] = "None"
    document["extractor"]["prior_project_involvement"] = "None"
    document["entries"] = [
        {
            "locus": "ORC-3",
            "element_kind": "field",
            "usage": "R",
            "cardinality": "1..1",
            "datatype": "EI",
            "max_length": None,
            "condition": None,
            "value_set_or_binding_ref": None,
            "source_grounding_classification": "SOURCE_FACT",
            "classification_rationale": "Requires a source-grounded filler order identifier.",
            "evidence": ["Edition 5 p.185"],
        },
        {
            "locus": "OBR-3",
            "element_kind": "field",
            "usage": "R",
            "cardinality": "1..1",
            "datatype": "EI",
            "max_length": None,
            "condition": None,
            "value_set_or_binding_ref": None,
            "source_grounding_classification": "SOURCE_FACT",
            "classification_rationale": "Same source-grounded order identity.",
            "evidence": ["Edition 5 p.189"],
        },
    ]
    document["extraction_complete"] = True
    return document


def test_repository_extraction_template_is_deliberately_not_ready() -> None:
    readiness = assess_required_element_extraction(_template())

    assert not readiness.ready
    assert any("not marked complete" in blocker for blocker in readiness.blockers)
    assert any("UNKNOWN" in blocker for blocker in readiness.blockers)
    assert any("UNRESOLVED" in blocker for blocker in readiness.blockers)


def test_independent_matching_extractions_have_full_exact_agreement() -> None:
    first = _complete("R-A")
    second = _complete("R-B")

    comparison = compare_required_element_extractions(first, second)
    report = extraction_comparison_to_dict(comparison)

    assert comparison.union_locus_count == 2
    assert comparison.exact_agreement_count == 2
    assert comparison.exact_agreement_rate == 1.0
    assert comparison.missing_from_a == ()
    assert comparison.missing_from_b == ()
    assert comparison.field_disagreements == ()
    assert report["adjudication_performed"] is False


def test_comparison_retains_field_disagreement_without_adjudicating() -> None:
    first = _complete("R-A")
    second = _complete("R-B")
    second["entries"][0]["source_grounding_classification"] = "DERIVED"

    comparison = compare_required_element_extractions(first, second)

    assert comparison.exact_agreement_rate == 0.5
    assert comparison.field_disagreements[0]["locus"] == "ORC-3"
    assert (
        comparison.field_disagreements[0]["differences"][
            "source_grounding_classification"
        ]["extractor_a"]
        == "SOURCE_FACT"
    )
    assert (
        comparison.field_disagreements[0]["differences"][
            "source_grounding_classification"
        ]["extractor_b"]
        == "DERIVED"
    )


def test_comparison_exposes_missing_required_locus() -> None:
    first = _complete("R-A")
    second = _complete("R-B")
    second["entries"].pop()

    comparison = compare_required_element_extractions(first, second)

    assert comparison.missing_from_b == ("OBR-3",)
    assert comparison.union_locus_count == 2
    assert comparison.exact_agreement_rate == 0.5


def test_comparison_rejects_same_reviewer_or_different_source_artifact() -> None:
    first = _complete("R-A")
    second = _complete("R-A")

    with pytest.raises(ValueError, match="different extractor IDs"):
        compare_required_element_extractions(first, second)

    second = _complete("R-B")
    second["source"]["artifact_sha256"] = "1" * 64

    with pytest.raises(ValueError, match="pinned Edition 5 guide"):
        compare_required_element_extractions(first, second)


def test_comparison_rejects_different_errata_artifact_hashes() -> None:
    first = _complete("R-A")
    second = _complete("R-B")
    second["source"]["errata_artifact_sha256"] = "1" * 64

    with pytest.raises(ValueError, match="pinned 2024DEC errata"):
        compare_required_element_extractions(first, second)


def test_comparison_report_retains_both_document_hashes() -> None:
    first = _complete("R-A")
    second = _complete("R-B")
    report = extraction_comparison_to_dict(
        compare_required_element_extractions(first, second)
    )
    assert report["source_sha256"] == first["source"]["artifact_sha256"]
    assert report["errata_sha256"] == first["source"]["errata_artifact_sha256"]


def test_extraction_independence_flags_are_fail_closed() -> None:
    document = _complete("R-A")
    mutated = deepcopy(document)
    mutated["independence"][
        "project_required_element_inventory_seen_before_completion"
    ] = True

    readiness = assess_required_element_extraction(mutated)

    assert not readiness.ready
    assert any("independence condition failed" in blocker for blocker in readiness.blockers)
