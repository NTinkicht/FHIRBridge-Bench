"""Independent error-precedence review comparison and adjudication seed."""

from __future__ import annotations

from typing import Any


def _reviewer_id(response: dict[str, Any]) -> str:
    reviewer = response.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("precedence response must contain reviewer metadata")
    reviewer_id = reviewer.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        raise ValueError("precedence reviewer_id must be non-empty")
    return reviewer_id


def compare_precedence_responses(
    response_a: dict[str, Any],
    response_b: dict[str, Any],
) -> dict[str, Any]:
    for response in (response_a, response_b):
        if response.get("assignment_id") != "FHIRBRIDGE-PRECEDENCE-BLIND-001":
            raise ValueError("precedence response references wrong assignment")
    reviewer_a = _reviewer_id(response_a)
    reviewer_b = _reviewer_id(response_b)
    if reviewer_a == reviewer_b:
        raise ValueError("precedence review requires distinct reviewer IDs")

    decision_a = str(response_a.get("decision"))
    decision_b = str(response_b.get("decision"))
    return {
        "assignment_id": "FHIRBRIDGE-PRECEDENCE-BLIND-001",
        "reviewer_a_id": reviewer_a,
        "reviewer_b_id": reviewer_b,
        "reviewer_a_decision": decision_a,
        "reviewer_b_decision": decision_b,
        "initial_agreement": decision_a == decision_b,
        "adjudication_performed": False,
    }


def build_precedence_adjudication_seed(
    response_a: dict[str, Any],
    response_b: dict[str, Any],
    *,
    candidate_policy_sha256: str,
    reviewer_a_response_sha256: str,
    reviewer_b_response_sha256: str,
) -> dict[str, Any]:
    pair = compare_precedence_responses(response_a, response_b)
    for label, value in (
        ("candidate_policy_sha256", candidate_policy_sha256),
        ("reviewer_a_response_sha256", reviewer_a_response_sha256),
        ("reviewer_b_response_sha256", reviewer_b_response_sha256),
    ):
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{label} must be a SHA-256 digest")

    reviewer_a = response_a["reviewer"]
    reviewer_b = response_b["reviewer"]
    return {
        "schema_version": "0.2.0",
        "review_id": "PRECEDENCE-REVIEW-TO-BE-ASSIGNED",
        "status": "incomplete_template",
        "created_at": None,
        "candidate_policy_sha256": candidate_policy_sha256,
        "blind_stage_evidence": {
            "assignment_id": pair["assignment_id"],
            "reviewer_a_response_sha256": reviewer_a_response_sha256,
            "reviewer_b_response_sha256": reviewer_b_response_sha256,
            "original_responses_retained": True,
            "other_reviewer_decisions_hidden_initially": True,
        },
        "reviewers": [
            {
                "reviewer_id": pair["reviewer_a_id"],
                "expertise": list(reviewer_a["expertise"]),
                "conflicts_of_interest": reviewer_a["conflicts_of_interest"],
                "prior_project_involvement": reviewer_a[
                    "prior_project_involvement"
                ],
            },
            {
                "reviewer_id": pair["reviewer_b_id"],
                "expertise": list(reviewer_b["expertise"]),
                "conflicts_of_interest": reviewer_b["conflicts_of_interest"],
                "prior_project_involvement": reviewer_b[
                    "prior_project_involvement"
                ],
            },
        ],
        "independent_decisions": [
            {
                "reviewer_id": pair["reviewer_a_id"],
                "decision": response_a["decision"],
                "rationale": response_a["rationale"],
            },
            {
                "reviewer_id": pair["reviewer_b_id"],
                "decision": response_b["decision"],
                "rationale": response_b["rationale"],
            },
        ],
        "adjudication": {
            "decision": "INDETERMINATE",
            "rationale": "TO_BE_COMPLETED_AFTER_INITIAL_RESPONSES_LOCKED",
        },
        "attestation": {
            "independent_initial_decisions": True,
            "other_reviewer_decisions_hidden_initially": True,
            "sealed_cases_used": False,
            "candidate_order_not_changed_during_adjudication": True,
        },
    }
