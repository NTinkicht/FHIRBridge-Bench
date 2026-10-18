import pytest

from fhirbridge.semantic_mapping_review import (
    mapping_review_pair_to_dict,
    paired_mapping_review_summary,
    validate_mapping_review_coverage,
)


def _assignment() -> dict:
    return {
        "assignment_id": "FHIRBRIDGE-SEMANTIC-MAPPING-REVIEW-001",
        "items": [
            {"candidate_id": "A"},
            {"candidate_id": "B"},
            {"candidate_id": "C"},
        ],
    }


def _response(reviewer_id: str, decisions: dict[str, tuple[str, str]]) -> dict:
    return {
        "assignment_id": "FHIRBRIDGE-SEMANTIC-MAPPING-REVIEW-001",
        "reviewer": {"reviewer_id": reviewer_id},
        "item_reviews": [
            {
                "candidate_id": candidate_id,
                "decision": decision,
                "profile_applicability": applicability,
            }
            for candidate_id, (decision, applicability) in sorted(
                decisions.items()
            )
        ],
    }


def test_mapping_review_pair_reports_agreement_without_adjudication() -> None:
    first = _response(
        "R-A",
        {
            "A": ("ACCEPT", "CONFIRMED"),
            "B": ("INDETERMINATE", "REQUIRES_EXACT_PROFILE"),
            "C": ("REJECT", "NOT_APPLICABLE"),
        },
    )
    second = _response(
        "R-B",
        {
            "A": ("ACCEPT", "CONFIRMED"),
            "B": ("INDETERMINATE", "REQUIRES_EXACT_PROFILE"),
            "C": ("REJECT", "NOT_APPLICABLE"),
        },
    )

    summary = paired_mapping_review_summary(_assignment(), first, second)
    report = mapping_review_pair_to_dict(summary)

    assert summary.decision_agreement.raw_agreement == 1.0
    assert summary.profile_applicability_agreement.raw_agreement == 1.0
    assert summary.disagreements == ()
    assert report["adjudication_performed"] is False
    assert report["decision_agreement"]["confusion_matrix"]["ACCEPT"]["ACCEPT"] == 1


def test_mapping_review_pair_retains_decision_and_profile_disagreements() -> None:
    first = _response(
        "R-A",
        {
            "A": ("ACCEPT", "CONFIRMED"),
            "B": ("ACCEPT", "CONFIRMED"),
            "C": ("REJECT", "NOT_APPLICABLE"),
        },
    )
    second = _response(
        "R-B",
        {
            "A": ("ACCEPT", "CONFIRMED"),
            "B": ("INDETERMINATE", "REQUIRES_EXACT_PROFILE"),
            "C": ("REJECT", "NOT_APPLICABLE"),
        },
    )

    summary = paired_mapping_review_summary(_assignment(), first, second)

    assert len(summary.disagreements) == 1
    disagreement = summary.disagreements[0]
    assert disagreement.candidate_id == "B"
    assert disagreement.reviewer_a_decision == "ACCEPT"
    assert disagreement.reviewer_b_decision == "INDETERMINATE"
    assert disagreement.reviewer_b_profile_applicability == (
        "REQUIRES_EXACT_PROFILE"
    )


def test_mapping_review_requires_complete_candidate_coverage() -> None:
    response = _response(
        "R-A",
        {
            "A": ("ACCEPT", "CONFIRMED"),
            "B": ("ACCEPT", "CONFIRMED"),
        },
    )

    with pytest.raises(ValueError, match="complete candidate set"):
        validate_mapping_review_coverage(response, _assignment())


def test_mapping_review_pair_requires_distinct_reviewers() -> None:
    decisions = {
        "A": ("ACCEPT", "CONFIRMED"),
        "B": ("ACCEPT", "CONFIRMED"),
        "C": ("REJECT", "NOT_APPLICABLE"),
    }

    with pytest.raises(ValueError, match="distinct reviewer IDs"):
        paired_mapping_review_summary(
            _assignment(),
            _response("R-A", decisions),
            _response("R-A", decisions),
        )


def test_mapping_review_rejects_wrong_assignment_id() -> None:
    response = _response(
        "R-A",
        {
            "A": ("ACCEPT", "CONFIRMED"),
            "B": ("ACCEPT", "CONFIRMED"),
            "C": ("REJECT", "NOT_APPLICABLE"),
        },
    )
    response["assignment_id"] = "OTHER"

    with pytest.raises(ValueError, match="wrong assignment"):
        validate_mapping_review_coverage(response, _assignment())
