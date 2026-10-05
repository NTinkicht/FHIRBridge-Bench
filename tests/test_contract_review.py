import pytest

from fhirbridge.contract_review import decisions_by_rule, paired_review_summary


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
