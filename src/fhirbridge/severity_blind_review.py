"""Independent blind severity-review coverage and pair comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SeverityRatingDisagreement:
    anchor_id: str
    reviewer_a_severity: str
    reviewer_b_severity: str


@dataclass(frozen=True)
class SeverityBlindPairSummary:
    assignment_id: str
    reviewer_a_id: str
    reviewer_b_id: str
    anchor_ids: tuple[str, ...]
    exact_agreement_count: int
    exact_agreement_rate: float
    disagreement_anchor_ids: tuple[str, ...]
    disagreements: tuple[SeverityRatingDisagreement, ...]


def _reviewer_id(response: dict[str, Any]) -> str:
    reviewer = response.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("severity response must contain reviewer metadata")
    reviewer_id = reviewer.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        raise ValueError("reviewer.reviewer_id must be a non-empty string")
    return reviewer_id


def expected_anchor_ids(anchor_set: dict[str, Any]) -> tuple[str, ...]:
    anchors = anchor_set.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("severity anchor set must contain anchors")
    observed: set[str] = set()
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ValueError("severity anchor is malformed")
        anchor_id = anchor.get("anchor_id")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise ValueError("severity anchor requires anchor_id")
        if anchor_id in observed:
            raise ValueError(f"duplicate severity anchor_id: {anchor_id}")
        observed.add(anchor_id)
    return tuple(sorted(observed))


def _ratings_by_anchor(
    response: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    ratings = response.get("anchor_ratings")
    if not isinstance(ratings, list) or not ratings:
        raise ValueError("anchor_ratings must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for rating in ratings:
        if not isinstance(rating, dict):
            raise ValueError("severity anchor rating is malformed")
        anchor_id = rating.get("anchor_id")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise ValueError("severity anchor rating requires anchor_id")
        if anchor_id in result:
            raise ValueError(f"duplicate severity rating: {anchor_id}")
        result[anchor_id] = rating
    return result


def validate_blind_severity_coverage(
    response: dict[str, Any],
    anchor_set: dict[str, Any],
) -> None:
    if response.get("assignment_id") != "FHIRBRIDGE-SEVERITY-BLIND-001":
        raise ValueError("severity response references the wrong assignment")
    expected = set(expected_anchor_ids(anchor_set))
    observed = set(_ratings_by_anchor(response))
    if expected != observed:
        raise ValueError(
            "severity response does not cover the complete anchor set; "
            f"missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )


def paired_blind_severity_summary(
    response_a: dict[str, Any],
    response_b: dict[str, Any],
    anchor_set: dict[str, Any],
) -> SeverityBlindPairSummary:
    validate_blind_severity_coverage(response_a, anchor_set)
    validate_blind_severity_coverage(response_b, anchor_set)

    reviewer_a = _reviewer_id(response_a)
    reviewer_b = _reviewer_id(response_b)
    if reviewer_a == reviewer_b:
        raise ValueError("severity pair requires distinct reviewer IDs")

    ratings_a = _ratings_by_anchor(response_a)
    ratings_b = _ratings_by_anchor(response_b)
    anchor_ids = expected_anchor_ids(anchor_set)
    disagreements: list[SeverityRatingDisagreement] = []
    exact = 0
    for anchor_id in anchor_ids:
        left = str(ratings_a[anchor_id].get("severity"))
        right = str(ratings_b[anchor_id].get("severity"))
        if left == right:
            exact += 1
        else:
            disagreements.append(
                SeverityRatingDisagreement(
                    anchor_id=anchor_id,
                    reviewer_a_severity=left,
                    reviewer_b_severity=right,
                )
            )

    return SeverityBlindPairSummary(
        assignment_id="FHIRBRIDGE-SEVERITY-BLIND-001",
        reviewer_a_id=reviewer_a,
        reviewer_b_id=reviewer_b,
        anchor_ids=anchor_ids,
        exact_agreement_count=exact,
        exact_agreement_rate=exact / len(anchor_ids),
        disagreement_anchor_ids=tuple(
            item.anchor_id for item in disagreements
        ),
        disagreements=tuple(disagreements),
    )


def build_severity_adjudication_seed(
    response_a: dict[str, Any],
    response_b: dict[str, Any],
    anchor_set: dict[str, Any],
    *,
    candidate_policy_sha256: str,
    reviewer_a_response_sha256: str,
    reviewer_b_response_sha256: str,
) -> dict[str, Any]:
    """Build a post-blind adjudication seed without deciding disputed ratings."""

    summary = paired_blind_severity_summary(
        response_a,
        response_b,
        anchor_set,
    )
    if (
        len(candidate_policy_sha256) != 64
        or len(reviewer_a_response_sha256) != 64
        or len(reviewer_b_response_sha256) != 64
    ):
        raise ValueError("severity adjudication hashes must be SHA-256 digests")

    anchors_by_id = {
        anchor["anchor_id"]: anchor
        for anchor in anchor_set["anchors"]
    }
    ratings_a = _ratings_by_anchor(response_a)
    ratings_b = _ratings_by_anchor(response_b)
    reviewer_a = response_a["reviewer"]
    reviewer_b = response_b["reviewer"]

    anchor_reviews: list[dict[str, Any]] = []
    for anchor_id in summary.anchor_ids:
        design = anchors_by_id[anchor_id]
        visible = design["reviewer_visible"]
        anchor_reviews.append(
            {
                "anchor_id": anchor_id,
                "anchor_description": visible["vignette"],
                "expected_boundary_role": design[
                    "expected_boundary_role_internal"
                ],
                "reviewer_ratings": [
                    {
                        "reviewer_id": summary.reviewer_a_id,
                        "severity": ratings_a[anchor_id]["severity"],
                        "rationale": ratings_a[anchor_id]["rationale"],
                    },
                    {
                        "reviewer_id": summary.reviewer_b_id,
                        "severity": ratings_b[anchor_id]["severity"],
                        "rationale": ratings_b[anchor_id]["rationale"],
                    },
                ],
                "adjudicated_severity": "INDETERMINATE",
                "adjudication_rationale": (
                    "TO_BE_COMPLETED_AFTER_BLIND_RESPONSES_LOCKED"
                ),
            }
        )

    return {
        "schema_version": "0.2.0",
        "calibration_id": "SEVERITY-CALIBRATION-TO-BE-ASSIGNED",
        "status": "incomplete_template",
        "created_at": None,
        "candidate_policy_sha256": candidate_policy_sha256,
        "blind_stage_evidence": {
            "assignment_id": summary.assignment_id,
            "reviewer_a_response_sha256": reviewer_a_response_sha256,
            "reviewer_b_response_sha256": reviewer_b_response_sha256,
            "original_responses_retained": True,
            "boundary_roles_hidden_initially": True,
        },
        "reviewers": [
            {
                "reviewer_id": summary.reviewer_a_id,
                "expertise": list(reviewer_a["expertise"]),
                "conflicts_of_interest": reviewer_a["conflicts_of_interest"],
                "prior_project_involvement": reviewer_a[
                    "prior_project_involvement"
                ],
            },
            {
                "reviewer_id": summary.reviewer_b_id,
                "expertise": list(reviewer_b["expertise"]),
                "conflicts_of_interest": reviewer_b["conflicts_of_interest"],
                "prior_project_involvement": reviewer_b[
                    "prior_project_involvement"
                ],
            },
        ],
        "anchor_reviews": anchor_reviews,
        "pre_adjudication_agreement": {
            "anchor_count": len(summary.anchor_ids),
            "exact_agreement_count": summary.exact_agreement_count,
            "exact_agreement_rate": summary.exact_agreement_rate,
            "disagreement_anchor_ids": list(
                summary.disagreement_anchor_ids
            ),
        },
        "major_threshold_decision": {
            "threshold": "S2_or_higher",
            "included_levels": ["S2", "S3"],
            "rationale": "TO_BE_DECIDED_AFTER_ANCHOR_ADJUDICATION",
            "decision_status": "frozen_for_confirmatory_endpoint",
        },
        "attestation": {
            "independent_initial_ratings": True,
            "sealed_cases_used": False,
            "adjudication_after_initial_ratings": True,
            "all_disagreements_retained": True,
        },
    }
