"""Fail-closed extraction metadata tests; passing does not prove standard coverage."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_required_element_review import assess_required_element_extraction

_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/extraction_template.yaml"
)


def _declared_complete() -> dict:
    result = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    result["extraction_id"] = "EXT-QUALIFIED-FIXTURE"
    result["extractor"]["extractor_id"] = "INDEPENDENT-EXTRACTOR-A"
    result["entries"] = [
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
            "classification_rationale": "Requires source order identity.",
            "evidence": ["Edition 5 p.185"],
        }
    ]
    result["extraction_complete"] = True
    return result


def test_valid_fixture_has_no_metadata_blockers_not_completeness_certification() -> None:
    assert assess_required_element_extraction(_declared_complete()).ready


@pytest.mark.parametrize(
    ("path", "value", "blocker"),
    [
        (("schema_version",), "0.0.0", "schema_version"),
        (("extraction_id",), "TO_BE_ASSIGNED", "extraction_id"),
        (("extractor", "extractor_id"), "TO_BE_ASSIGNED", "extractor_id"),
        (("source", "artifact_sha256"), "z" * 64, "SHA-256"),
        (("source", "artifact_sha256"), "0" * 64, "SHA-256"),
        (("source", "artifact_sha256"), "1" * 64, "pinned Edition 5 guide"),
        (("source", "errata_artifact_sha256"), None, "errata artifact SHA-256"),
        (("source", "errata_artifact_sha256"), "z" * 64, "errata artifact SHA-256"),
        (("source", "errata_artifact_sha256"), "0" * 64, "errata artifact SHA-256"),
        (("source", "errata_artifact_sha256"), "1" * 64, "pinned 2024DEC errata"),
        (("source", "artifact_type"), "edition5_machine_profile_bundle", "Path B PDF source"),
        (("source", "profile_name"), "LRI_NDBS_Profile", "target profile"),
        (("source", "edition"), "4", "Edition 5/2024DEC"),
        (("source", "artifact_type"), "legacy_nist_profile", "artifact type"),
        (("source", "components"), ["LAB_FRU_Component"], "component set"),
        (("entries", 0, "cardinality"), "TO_BE_EXTRACTED", "cardinality"),
        (("entries", 0, "evidence"), ["  "], "evidence"),
        (("entries", 0, "condition"), "TO_BE_EXTRACTED", "condition"),
        (("entries", 0, "locus"), "TO_BE_EXTRACTED", "locus"),
        (("entries", 0, "classification_rationale"), "TBD", "classification_rationale"),
        (("entries", 0, "classification_rationale"), None, "classification_rationale"),
        (("entries", 0, "classification_rationale"), "", "classification_rationale"),
    ],
)
def test_unfinished_metadata_is_never_freeze_ready(
    path: tuple[str | int, ...], value: object, blocker: str
) -> None:
    doc = deepcopy(_declared_complete())
    parent: object = doc
    for piece in path[:-1]:
        parent = parent[piece]
    parent[path[-1]] = value
    result = assess_required_element_extraction(doc)

    assert not result.ready
    assert any(blocker in item for item in result.blockers)


def test_conditional_requiredness_without_predicate_is_blocked() -> None:
    doc = _declared_complete()
    doc["entries"][0]["usage"] = "C"
    doc["entries"][0]["condition"] = None

    result = assess_required_element_extraction(doc)

    assert not result.ready
    assert any("conditional usage has no condition" in item for item in result.blockers)


def test_condition_with_source_rationale_can_be_assessed_without_claiming_coverage() -> None:
    doc = _declared_complete()
    doc["entries"][0]["usage"] = "C"
    doc["entries"][0]["condition"] = "See Edition 5 condition predicate cited in evidence"

    assert assess_required_element_extraction(doc).ready


def test_omitted_classification_rationale_blocks_readiness_and_pair_comparison() -> None:
    from fhirbridge.lri_required_element_review import (
        compare_required_element_extractions,
    )

    left = _declared_complete()
    right = deepcopy(left)
    right["extractor"]["extractor_id"] = "INDEPENDENT-EXTRACTOR-B"
    left["entries"][0].pop("classification_rationale")

    result = assess_required_element_extraction(left)
    assert not result.ready
    assert any("classification_rationale" in blocker for blocker in result.blockers)

    with pytest.raises(ValueError, match="extraction A is not ready"):
        compare_required_element_extractions(left, right)
