import pytest

from fhirbridge.precedence_blind_review import (
    build_precedence_adjudication_seed,
    compare_precedence_responses,
)


def _response(reviewer_id: str, decision: str = "ACCEPT") -> dict:
    return {
        "schema_version": "0.1.0",
        "assignment_id": "FHIRBRIDGE-PRECEDENCE-BLIND-001",
        "reviewer": {
            "reviewer_id": reviewer_id,
            "review_date": "2026-10-20",
            "expertise": ["HL7 interoperability"],
            "conflicts_of_interest": "None declared",
            "prior_project_involvement": "None",
        },
        "decision": decision,
        "rationale": f"Independent {decision} rationale.",
        "attestation": {
            "independent_initial_decision": True,
            "other_reviewer_decision_hidden": True,
            "sealed_cases_not_used": True,
            "renderer_outputs_not_used_as_correctness_evidence": True,
        },
    }


def test_precedence_pair_retains_initial_disagreement() -> None:
    pair = compare_precedence_responses(
        _response("R-A", "ACCEPT"),
        _response("R-B", "REJECT"),
    )

    assert pair["initial_agreement"] is False
    assert pair["reviewer_a_decision"] == "ACCEPT"
    assert pair["reviewer_b_decision"] == "REJECT"
    assert pair["adjudication_performed"] is False


def test_precedence_pair_requires_distinct_reviewers() -> None:
    with pytest.raises(ValueError, match="distinct reviewer IDs"):
        compare_precedence_responses(
            _response("R-A"),
            _response("R-A"),
        )


def test_precedence_pair_rejects_wrong_assignment() -> None:
    response = _response("R-A")
    response["assignment_id"] = "OTHER"

    with pytest.raises(ValueError, match="wrong assignment"):
        compare_precedence_responses(response, _response("R-B"))


def test_precedence_adjudication_seed_preserves_blind_hashes() -> None:
    seed = build_precedence_adjudication_seed(
        _response("R-A", "ACCEPT"),
        _response("R-B", "REJECT"),
        candidate_policy_sha256="a" * 64,
        reviewer_a_response_sha256="b" * 64,
        reviewer_b_response_sha256="c" * 64,
    )

    assert seed["schema_version"] == "0.2.0"
    assert seed["blind_stage_evidence"] == {
        "assignment_id": "FHIRBRIDGE-PRECEDENCE-BLIND-001",
        "reviewer_a_response_sha256": "b" * 64,
        "reviewer_b_response_sha256": "c" * 64,
        "original_responses_retained": True,
        "other_reviewer_decisions_hidden_initially": True,
    }
    assert seed["adjudication"]["decision"] == "INDETERMINATE"
    assert "TO_BE_COMPLETED" in seed["adjudication"]["rationale"]


def test_precedence_adjudication_seed_keeps_both_initial_decisions() -> None:
    seed = build_precedence_adjudication_seed(
        _response("R-A", "ACCEPT"),
        _response("R-B", "REJECT"),
        candidate_policy_sha256="a" * 64,
        reviewer_a_response_sha256="b" * 64,
        reviewer_b_response_sha256="c" * 64,
    )

    decisions = {
        item["reviewer_id"]: item["decision"]
        for item in seed["independent_decisions"]
    }
    assert decisions == {"R-A": "ACCEPT", "R-B": "REJECT"}
