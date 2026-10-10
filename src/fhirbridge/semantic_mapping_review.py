"""Compare independent external reviews of status/specimen mapping candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agreement import AgreementResult, agreement_statistics


@dataclass(frozen=True)
class MappingReviewDisagreement:
    candidate_id: str
    reviewer_a_decision: str
    reviewer_b_decision: str
    reviewer_a_profile_applicability: str
    reviewer_b_profile_applicability: str


@dataclass(frozen=True)
class MappingReviewPairSummary:
    assignment_id: str
    reviewer_a_id: str
    reviewer_b_id: str
    candidate_ids: tuple[str, ...]
    decision_agreement: AgreementResult
    profile_applicability_agreement: AgreementResult
    disagreements: tuple[MappingReviewDisagreement, ...]


def _reviewer_id(response: dict[str, Any]) -> str:
    reviewer = response.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("mapping review response must contain reviewer metadata")
    reviewer_id = reviewer.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        raise ValueError("reviewer.reviewer_id must be a non-empty string")
    return reviewer_id


def _reviews_by_candidate(
    response: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    reviews = response.get("item_reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("item_reviews must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("each item review must be an object")
        candidate_id = review.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("each item review requires candidate_id")
        if candidate_id in result:
            raise ValueError(f"duplicate mapping review: {candidate_id}")
        result[candidate_id] = review
    return result


def expected_mapping_candidate_ids(
    assignment: dict[str, Any],
) -> tuple[str, ...]:
    items = assignment.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("semantic mapping assignment must contain items")
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("semantic mapping assignment item must be an object")
        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("assignment item requires candidate_id")
        if candidate_id in ids:
            raise ValueError(f"duplicate mapping candidate: {candidate_id}")
        ids.add(candidate_id)
    return tuple(sorted(ids))


def validate_mapping_review_coverage(
    response: dict[str, Any],
    assignment: dict[str, Any],
) -> None:
    if response.get("assignment_id") != assignment.get("assignment_id"):
        raise ValueError("mapping review response references the wrong assignment")
    expected = set(expected_mapping_candidate_ids(assignment))
    observed = set(_reviews_by_candidate(response))
    if expected != observed:
        raise ValueError(
            "mapping review does not cover the complete candidate set; "
            f"missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )


def paired_mapping_review_summary(
    assignment: dict[str, Any],
    response_a: dict[str, Any],
    response_b: dict[str, Any],
) -> MappingReviewPairSummary:
    validate_mapping_review_coverage(response_a, assignment)
    validate_mapping_review_coverage(response_b, assignment)

    reviewer_a = _reviewer_id(response_a)
    reviewer_b = _reviewer_id(response_b)
    if reviewer_a == reviewer_b:
        raise ValueError("mapping review pair requires distinct reviewer IDs")

    reviews_a = _reviews_by_candidate(response_a)
    reviews_b = _reviews_by_candidate(response_b)
    candidate_ids = expected_mapping_candidate_ids(assignment)

    decisions_a: list[str] = []
    decisions_b: list[str] = []
    applicability_a: list[str] = []
    applicability_b: list[str] = []
    disagreements: list[MappingReviewDisagreement] = []

    for candidate_id in candidate_ids:
        review_a = reviews_a[candidate_id]
        review_b = reviews_b[candidate_id]
        decision_a = str(review_a.get("decision"))
        decision_b = str(review_b.get("decision"))
        profile_a = str(review_a.get("profile_applicability"))
        profile_b = str(review_b.get("profile_applicability"))
        decisions_a.append(decision_a)
        decisions_b.append(decision_b)
        applicability_a.append(profile_a)
        applicability_b.append(profile_b)
        if decision_a != decision_b or profile_a != profile_b:
            disagreements.append(
                MappingReviewDisagreement(
                    candidate_id=candidate_id,
                    reviewer_a_decision=decision_a,
                    reviewer_b_decision=decision_b,
                    reviewer_a_profile_applicability=profile_a,
                    reviewer_b_profile_applicability=profile_b,
                )
            )

    return MappingReviewPairSummary(
        assignment_id=str(assignment["assignment_id"]),
        reviewer_a_id=reviewer_a,
        reviewer_b_id=reviewer_b,
        candidate_ids=candidate_ids,
        decision_agreement=agreement_statistics(decisions_a, decisions_b),
        profile_applicability_agreement=agreement_statistics(
            applicability_a,
            applicability_b,
        ),
        disagreements=tuple(disagreements),
    )


def mapping_review_pair_to_dict(
    summary: MappingReviewPairSummary,
) -> dict[str, Any]:
    def agreement_dict(result: AgreementResult) -> dict[str, Any]:
        return {
            "n": result.n,
            "raw_agreement": result.raw_agreement,
            "cohens_kappa": result.cohens_kappa,
            "gwets_ac1": result.gwets_ac1,
            "labels": list(result.labels),
            "confusion_matrix": [
                list(row) for row in result.confusion_matrix
            ],
        }

    return {
        "assignment_id": summary.assignment_id,
        "reviewer_a_id": summary.reviewer_a_id,
        "reviewer_b_id": summary.reviewer_b_id,
        "candidate_ids": list(summary.candidate_ids),
        "decision_agreement": agreement_dict(summary.decision_agreement),
        "profile_applicability_agreement": agreement_dict(
            summary.profile_applicability_agreement
        ),
        "disagreements": [
            {
                "candidate_id": item.candidate_id,
                "reviewer_a_decision": item.reviewer_a_decision,
                "reviewer_b_decision": item.reviewer_b_decision,
                "reviewer_a_profile_applicability": (
                    item.reviewer_a_profile_applicability
                ),
                "reviewer_b_profile_applicability": (
                    item.reviewer_b_profile_applicability
                ),
            }
            for item in summary.disagreements
        ],
        "adjudication_performed": False,
    }
