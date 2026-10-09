import pytest

from fhirbridge.contract_review import (
    decisions_by_rule,
    expected_review_rule_ids,
    paired_review_summary,
    validate_complete_review_response,
)
from fhirbridge.schema_validation import load_yaml


def _response(reviewer_id: str, decisions: dict[str, str]) -> dict:
    return {
        "reviewer": {"reviewer_id": reviewer_id},
        "contract": {"id": "F2V-LAB-ORU-R01-001", "version": "0.2.0"},
        "rule_reviews": [
            {"rule_id": rule_id, "projectability_decision": decision}
            for rule_id, decision in decisions.items()
        ],
    }


def test_decisions_by_rule_preserves_original_labels() -> None:
    response = _response(
        "R1",
        {
            "PATIENT_IDENTIFIER_001": "MUST_PRESERVE",
            "PATIENT_NAME_001": "MAY_TRANSFORM",
        },
    )

    assert decisions_by_rule(response) == {
        "PATIENT_IDENTIFIER_001": "MUST_PRESERVE",
        "PATIENT_NAME_001": "MAY_TRANSFORM",
    }


def test_paired_review_summary_reports_agreement_and_disagreements() -> None:
    first = _response(
        "R1",
        {
            "PATIENT_IDENTIFIER_001": "MUST_PRESERVE",
            "PATIENT_NAME_001": "MAY_TRANSFORM",
            "REPORT_CODE_001": "MUST_PRESERVE",
        },
    )
    second = _response(
        "R2",
        {
            "PATIENT_IDENTIFIER_001": "MUST_PRESERVE",
            "PATIENT_NAME_001": "INDETERMINATE",
            "REPORT_CODE_001": "MUST_PRESERVE",
        },
    )

    summary = paired_review_summary(first, second)

    assert summary.contract_id == "F2V-LAB-ORU-R01-001"
    assert summary.contract_version == "0.2.0"
    assert summary.reviewer_a_id == "R1"
    assert summary.reviewer_b_id == "R2"
    assert summary.agreement.n == 3
    assert summary.agreement.raw_agreement == pytest.approx(2 / 3)
    assert len(summary.disagreements) == 1
    assert summary.disagreements[0].rule_id == "PATIENT_NAME_001"
    assert summary.disagreements[0].reviewer_a_decision == "MAY_TRANSFORM"
    assert summary.disagreements[0].reviewer_b_decision == "INDETERMINATE"


def test_paired_review_summary_rejects_different_contract_versions() -> None:
    first = _response("R1", {"RULE": "MUST_PRESERVE"})
    second = _response("R2", {"RULE": "MUST_PRESERVE"})
    second["contract"]["version"] = "0.3.0"

    with pytest.raises(ValueError, match="same contract ID and version"):
        paired_review_summary(first, second)


def test_paired_review_summary_rejects_missing_rules() -> None:
    first = _response(
        "R1",
        {"RULE_A": "MUST_PRESERVE", "RULE_B": "MAY_TRANSFORM"},
    )
    second = _response("R2", {"RULE_A": "MUST_PRESERVE"})

    with pytest.raises(ValueError, match="same rule set"):
        paired_review_summary(first, second)


def test_duplicate_rule_reviews_are_rejected() -> None:
    response = _response("R1", {"RULE_A": "MUST_PRESERVE"})
    response["rule_reviews"].append(
        {"rule_id": "RULE_A", "projectability_decision": "INDETERMINATE"}
    )

    with pytest.raises(ValueError, match="duplicate rule review"):
        decisions_by_rule(response)


def test_same_reviewer_cannot_be_used_as_independent_pair() -> None:
    first = _response("R1", {"RULE_A": "MUST_PRESERVE"})
    second = _response("R1", {"RULE_A": "MUST_PRESERVE"})

    with pytest.raises(ValueError, match="distinct reviewer IDs"):
        paired_review_summary(first, second)


_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"
_RELATIONSHIP_CANDIDATES = "contracts/review/relationship_candidates_v0.1.yaml"


def _complete_response(reviewer_id: str, *, include_candidates: bool = True) -> dict:
    contract = load_yaml(_CONTRACT_PATH)
    candidates = load_yaml(_RELATIONSHIP_CANDIDATES) if include_candidates else None
    expected = expected_review_rule_ids(
        contract,
        relationship_candidates=candidates,
    )
    operations_by_rule = {
        rule["rule_id"]: set(rule.get("allowed_operations", []))
        for rule in contract["rules"]
        if rule.get("expert_review_required") is True
    }
    if candidates is not None:
        operations_by_rule.update(
            {
                item["candidate_rule_id"]: set(
                    item.get("proposed_allowed_operations", [])
                )
                for item in candidates["candidates"]
            }
        )
    return {
        "reviewer": {"reviewer_id": reviewer_id},
        "contract": {"id": "F2V-LAB-ORU-R01-001", "version": "0.2.0"},
        "rule_reviews": [
            {
                "rule_id": rule_id,
                "projectability_decision": "INDETERMINATE",
                "accepted_operations": sorted(operations_by_rule[rule_id]),
                "rejected_operations": [],
            }
            for rule_id in expected
        ],
    }


def test_expected_review_set_includes_contract_and_relationship_candidates() -> None:
    contract = load_yaml(_CONTRACT_PATH)
    candidates = load_yaml(_RELATIONSHIP_CANDIDATES)

    expected = expected_review_rule_ids(
        contract,
        relationship_candidates=candidates,
    )

    assert "PATIENT_IDENTIFIER_001" in expected
    assert "FREE_TEXT_INFERENCE_001" in expected
    assert "REPORT_RESULT_MEMBERSHIP_001" in expected
    assert "OBSERVATION_SUBJECT_ATTRIBUTION_001" in expected
    assert "REPORT_SPECIMEN_MEMBERSHIP_001" in expected
    assert "OBSERVATION_SPECIMEN_MEMBERSHIP_001" in expected


def test_complete_review_response_rejects_identically_missing_rule() -> None:
    contract = load_yaml(_CONTRACT_PATH)
    candidates = load_yaml(_RELATIONSHIP_CANDIDATES)
    response = _complete_response("R1")
    response["rule_reviews"] = response["rule_reviews"][1:]

    with pytest.raises(ValueError, match="complete frozen review set"):
        validate_complete_review_response(
            response,
            contract,
            relationship_candidates=candidates,
        )


def test_complete_review_response_rejects_unexpected_rule() -> None:
    contract = load_yaml(_CONTRACT_PATH)
    candidates = load_yaml(_RELATIONSHIP_CANDIDATES)
    response = _complete_response("R1")
    response["rule_reviews"].append(
        {
            "rule_id": "INVENTED_RULE",
            "projectability_decision": "INDETERMINATE",
            "accepted_operations": [],
            "rejected_operations": [],
        }
    )

    with pytest.raises(ValueError, match="unexpected"):
        validate_complete_review_response(
            response,
            contract,
            relationship_candidates=candidates,
        )


def test_complete_review_requires_explicit_operation_partition() -> None:
    contract = load_yaml(_CONTRACT_PATH)
    candidates = load_yaml(_RELATIONSHIP_CANDIDATES)
    response = _complete_response("R1")
    patient_identifier = next(
        item
        for item in response["rule_reviews"]
        if item["rule_id"] == "PATIENT_IDENTIFIER_001"
    )
    assert patient_identifier["accepted_operations"]
    patient_identifier["accepted_operations"] = []

    with pytest.raises(ValueError, match="operation review must partition"):
        validate_complete_review_response(
            response,
            contract,
            relationship_candidates=candidates,
        )


def test_complete_review_response_accepts_full_explicit_review_set() -> None:
    contract = load_yaml(_CONTRACT_PATH)
    candidates = load_yaml(_RELATIONSHIP_CANDIDATES)
    response = _complete_response("R1")

    validate_complete_review_response(
        response,
        contract,
        relationship_candidates=candidates,
    )
