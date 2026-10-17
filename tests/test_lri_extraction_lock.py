"""First-round extraction response hashes are immutable inputs to comparison."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from fhirbridge.lri_extraction_lock import (
    compare_locked_extractions,
    create_response_lock,
    verify_response_lock,
)

_TEMPLATE = Path(
    "qualification/hl7v2/required_element_review/examples/extraction_template.yaml"
)


def _submission(identifier: str, *, complete: bool) -> bytes:
    doc = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    doc["extraction_id"] = f"EXT-{identifier}"
    doc["extractor"]["extractor_id"] = identifier
    if complete:
        doc["entries"] = [
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
                "classification_rationale": "Extracted test-only source justification",
                "evidence": ["Edition 5 test-only p.185"],
            }
        ]
        doc["extraction_complete"] = True
    return yaml.safe_dump(doc, sort_keys=False).encode("utf-8")


def test_lock_preserves_incomplete_first_round_without_fake_qualification() -> None:
    raw = _submission("R-A", complete=False)
    record = create_response_lock(raw)
    assert record["status"] == "RESPONSE_HASHED_NOT_HUMAN_ATTESTED"
    assert record["initial_extraction_metadata_ready"] is False
    assert record["qualified_G1"] is False
    assert record["adjudication_performed"] is False
    assert verify_response_lock(raw, record)["extraction_complete"] is False


def test_original_response_bytes_cannot_change_without_detection() -> None:
    raw = _submission("R-A", complete=True)
    record = create_response_lock(raw)
    with pytest.raises(ValueError, match="original complete lock"):
        verify_response_lock(raw + b"\n# changed after initial submission\n", record)
    mutated = deepcopy(record)
    mutated["qualified_G1"] = True
    with pytest.raises(ValueError, match="original complete lock"):
        verify_response_lock(raw, mutated)


def test_locked_agreement_is_not_scientific_adjudication() -> None:
    raw_a = _submission("R-A", complete=True)
    raw_b = _submission("R-B", complete=True)
    outcome = compare_locked_extractions(
        raw_a, create_response_lock(raw_a), raw_b, create_response_lock(raw_b)
    )
    assert outcome["status"] == "LOCKED_UNADJUDICATED_COMPARISON_ONLY"
    assert outcome["comparison"]["exact_agreement_rate"] == 1.0
    assert outcome["comparison"]["adjudication_performed"] is False
    assert outcome["reviewer_independence_verified_by_software"] is False
    assert outcome["G1_qualified"] is False


def test_incomplete_locked_response_still_blocks_comparison() -> None:
    raw_a = _submission("R-A", complete=True)
    raw_b = _submission("R-B", complete=False)
    report = compare_locked_extractions(
        raw_a, create_response_lock(raw_a), raw_b, create_response_lock(raw_b)
    )
    assert report["status"] == "LOCKED_RESPONSES_NOT_READY_FOR_RULE_COMPARISON"
    assert report["readiness_blockers_b"]
    assert report["G1_qualified"] is False


def test_same_extractor_id_and_missing_independence_fail_closed() -> None:
    raw = _submission("R-A", complete=True)
    with pytest.raises(ValueError, match="different identifiers"):
        compare_locked_extractions(
            raw, create_response_lock(raw), raw, create_response_lock(raw)
        )
    doc = yaml.safe_load(raw)
    doc["independence"]["renderer_output_used_as_requirement_evidence"] = True
    with pytest.raises(ValueError, match="independence declarations"):
        create_response_lock(yaml.safe_dump(doc).encode("utf-8"))


def test_wrong_guide_hash_and_placeholder_identity_fail_before_lock() -> None:
    doc = yaml.safe_load(_submission("R-A", complete=True))
    doc["source"]["artifact_sha256"] = "1" * 64
    with pytest.raises(ValueError, match="pinned guide and errata"):
        create_response_lock(yaml.safe_dump(doc).encode("utf-8"))
    doc = yaml.safe_load(_submission("R-A", complete=True))
    doc["extractor"]["extractor_id"] = "TO_BE_ASSIGNED"
    with pytest.raises(ValueError, match="missing or placeholders"):
        create_response_lock(yaml.safe_dump(doc).encode("utf-8"))



@pytest.mark.parametrize(
    ("mutation", "detail"),
    [
        (
            lambda text: text + "\nschema_version: '0.2.0'\n",
            "duplicate top-level schema version",
        ),
        (
            lambda text: text.replace(
                "  artifact_sha256:", "  artifact_sha256: WRONG\n  artifact_sha256:", 1
            ),
            "duplicate source document hash",
        ),
        (
            lambda text: text.replace(
                "  renderer_output_used_as_requirement_evidence:",
                "  renderer_output_used_as_requirement_evidence: true\n"
                "  renderer_output_used_as_requirement_evidence:",
                1,
            ),
            "duplicate independence declaration",
        ),
        (
            lambda text: text.replace(
                "    usage: R", "    usage: X\n    usage: R", 1
            ),
            "duplicate requirement usage",
        ),
        (
            lambda text: text.replace(
                "source:\n",
                "source:\n  <<: &injected {artifact_type: unverified}\n",
                1,
            ),
            "unsafe YAML merge mapping",
        ),
    ],
)
def test_ambiguous_yaml_cannot_be_locked_even_if_last_value_looks_valid(
    mutation, detail: str,
) -> None:
    original = _submission("R-A", complete=True).decode("utf-8")
    suspect = mutation(original)
    assert suspect != original, detail
    with pytest.raises(ValueError, match="not valid UTF-8 YAML"):
        create_response_lock(suspect.encode("utf-8"))


def test_distinct_valid_nested_mapping_still_locks_and_verifies() -> None:
    original = _submission("R-A", complete=True)
    lock = create_response_lock(original)
    assert lock["initial_extraction_metadata_ready"] is True
    assert verify_response_lock(original, lock)["extractor"]["extractor_id"] == "R-A"
