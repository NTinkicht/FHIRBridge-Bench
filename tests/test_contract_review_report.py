from copy import deepcopy

import pytest

from fhirbridge.contract_review import expected_review_rule_ids
from fhirbridge.contract_review_report import build_contract_review_pair_report
from fhirbridge.schema_validation import load_yaml

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"
_CANDIDATES = "contracts/review/relationship_candidates_v0.1.yaml"


def _complete_response(reviewer_id: str) -> dict:
    contract = load_yaml(_CONTRACT)
    candidates = load_yaml(_CANDIDATES)
    expected = expected_review_rule_ids(
        contract,
        relationship_candidates=candidates,
    )

    operations_by_rule = {
        rule["rule_id"]: set(rule.get("allowed_operations", []))
        for rule in contract["rules"]
        if rule.get("expert_review_required") is True
    }
    operations_by_rule.update(
        {
            item["candidate_rule_id"]: set(
                item.get("proposed_allowed_operations", [])
            )
            for item in candidates["candidates"]
        }
    )

    return {
        "schema_version": "0.1.0",
        "reviewer": {
            "reviewer_id": reviewer_id,
            "expertise": ["HL7 v2/FHIR interoperability"],
            "review_date": "2026-10-10",
            "conflicts_of_interest": "None declared",
        },
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.2.0",
        },
        "rule_reviews": [
            {
                "rule_id": rule_id,
                "projectability_decision": "INDETERMINATE",
                "target_locus_defensible": "INDETERMINATE",
                "alternative_target_loci": [],
                "accepted_operations": sorted(operations_by_rule[rule_id]),
                "rejected_operations": [],
                "rejected_operation_reasons": {},
                "equivalence_adequate": "INDETERMINATE",
                "severity_plausible": "NOT_QUALIFIED",
                "evidence_sufficient": "PARTLY",
                "evidence_references": ["Independent standards review pending"],
                "main_concern": "",
                "confidence": "LOW",
            }
            for rule_id in expected
        ],
        "attestation": {
            "independent_initial_classification": True,
            "no_model_outputs_used": True,
            "no_verifier_outputs_used": True,
            "not_universal_mapping_endorsement": True,
        },
    }


def test_pair_report_hashes_original_reviews_and_surfaces_disagreement() -> None:
    contract = load_yaml(_CONTRACT)
    candidates = load_yaml(_CANDIDATES)
    first = _complete_response("EXT-R1")
    second = _complete_response("EXT-R2")
    second = deepcopy(second)
    second["rule_reviews"][0]["projectability_decision"] = "MUST_PRESERVE"

    report = build_contract_review_pair_report(
        first,
        second,
        contract=contract,
        relationship_candidates=candidates,
    )

    assert report["contract"] == {
        "id": "F2V-LAB-ORU-R01-001",
        "version": "0.2.0",
    }
    assert report["reviewers"] == {
        "reviewer_a_id": "EXT-R1",
        "reviewer_b_id": "EXT-R2",
    }
    assert report["rule_count"] == len(first["rule_reviews"])
    assert report["agreement"]["n"] == report["rule_count"]
    assert report["disagreement_count"] == 1
    assert report["adjudication_required"] is True
    assert report["original_reviews_preserved"] is True
    assert len(report["source_review_sha256"]["reviewer_a"]) == 64
    assert len(report["source_review_sha256"]["reviewer_b"]) == 64
    assert report["source_review_sha256"]["reviewer_a"] != report[
        "source_review_sha256"
    ]["reviewer_b"]


def test_pair_report_is_deterministic_for_identical_inputs() -> None:
    contract = load_yaml(_CONTRACT)
    candidates = load_yaml(_CANDIDATES)
    first = _complete_response("EXT-R1")
    second = _complete_response("EXT-R2")

    left = build_contract_review_pair_report(
        first,
        second,
        contract=contract,
        relationship_candidates=candidates,
    )
    right = build_contract_review_pair_report(
        first,
        second,
        contract=contract,
        relationship_candidates=candidates,
    )

    assert left == right
    assert left["disagreement_count"] == 0
    assert left["adjudication_required"] is False
    assert left["agreement"]["raw_agreement"] == pytest.approx(1.0)


def test_pair_report_rejects_incomplete_review_before_agreement() -> None:
    contract = load_yaml(_CONTRACT)
    candidates = load_yaml(_CANDIDATES)
    first = _complete_response("EXT-R1")
    second = _complete_response("EXT-R2")
    second = deepcopy(second)
    second["rule_reviews"] = second["rule_reviews"][1:]

    with pytest.raises(ValueError, match="complete frozen review set"):
        build_contract_review_pair_report(
            first,
            second,
            contract=contract,
            relationship_candidates=candidates,
        )
