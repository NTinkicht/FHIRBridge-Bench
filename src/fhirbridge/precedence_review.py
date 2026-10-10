"""Readiness checks for independent review of error-precedence policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class PrecedenceReviewReadiness:
    complete: bool
    accepted: bool
    initial_agreement: bool | None
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
        and set(value.lower()) != {"0"}
    )


def assess_precedence_review(
    document: dict[str, Any],
) -> PrecedenceReviewReadiness:
    blockers: list[str] = []

    if document.get("status") != "completed":
        blockers.append("precedence review is not marked completed")
    if document.get("created_at") is None:
        blockers.append("precedence review has no completion timestamp")
    if _placeholder(document.get("review_id")):
        blockers.append("precedence review_id is still a placeholder")
    if not _sha256(document.get("candidate_policy_sha256")):
        blockers.append("precedence candidate-policy SHA-256 is not frozen")

    reviewers = document.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        blockers.append("at least two precedence reviewers are required")
        reviewers = []

    reviewer_ids: set[str] = set()
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            blockers.append("precedence reviewer entry is malformed")
            continue
        reviewer_id = reviewer.get("reviewer_id")
        if (
            not isinstance(reviewer_id, str)
            or not reviewer_id
            or _placeholder(reviewer_id)
        ):
            blockers.append("precedence reviewer_id is incomplete")
            continue
        if reviewer_id in reviewer_ids:
            blockers.append(f"duplicate precedence reviewer_id: {reviewer_id}")
        reviewer_ids.add(reviewer_id)

        expertise = reviewer.get("expertise")
        if (
            not isinstance(expertise, list)
            or not expertise
            or any(
                not isinstance(item, str)
                or not item
                or _placeholder(item)
                for item in expertise
            )
        ):
            blockers.append(f"{reviewer_id}: expertise disclosure is incomplete")
        for field in ("conflicts_of_interest", "prior_project_involvement"):
            value = reviewer.get(field)
            if (
                not isinstance(value, str)
                or not value.strip()
                or _placeholder(value)
            ):
                blockers.append(f"{reviewer_id}: {field} disclosure is incomplete")

    decisions = document.get("independent_decisions")
    if not isinstance(decisions, list):
        blockers.append("independent precedence decisions are missing")
        decisions = []

    decision_by_reviewer: dict[str, str] = {}
    for item in decisions:
        if not isinstance(item, dict):
            blockers.append("precedence decision entry is malformed")
            continue
        reviewer_id = item.get("reviewer_id")
        decision = item.get("decision")
        rationale = item.get("rationale")
        if not isinstance(reviewer_id, str) or not reviewer_id:
            blockers.append("precedence decision lacks reviewer_id")
            continue
        if reviewer_id in decision_by_reviewer:
            blockers.append(
                f"duplicate precedence decision by reviewer {reviewer_id}"
            )
        if not isinstance(decision, str):
            blockers.append(f"{reviewer_id}: precedence decision is missing")
            continue
        decision_by_reviewer[reviewer_id] = decision
        if (
            not isinstance(rationale, str)
            or not rationale.strip()
            or _placeholder(rationale)
        ):
            blockers.append(
                f"{reviewer_id}: precedence decision rationale is incomplete"
            )

    if set(decision_by_reviewer) != reviewer_ids:
        blockers.append(
            "precedence decisions do not match the declared reviewer roster"
        )

    initial_agreement: bool | None
    if reviewer_ids and set(decision_by_reviewer) == reviewer_ids:
        initial_agreement = len(set(decision_by_reviewer.values())) == 1
    else:
        initial_agreement = None

    adjudication = document.get("adjudication")
    if not isinstance(adjudication, dict):
        blockers.append("precedence adjudication is missing")
        adjudicated = None
    else:
        adjudicated = adjudication.get("decision")
        rationale = adjudication.get("rationale")
        if adjudicated == "INDETERMINATE":
            blockers.append(
                "completed precedence review cannot remain INDETERMINATE"
            )
        if (
            not isinstance(rationale, str)
            or not rationale.strip()
            or _placeholder(rationale)
        ):
            blockers.append("precedence adjudication rationale is incomplete")

    attestation = document.get("attestation")
    if not isinstance(attestation, dict):
        blockers.append("precedence review attestation is missing")
    else:
        expected = {
            "independent_initial_decisions": True,
            "other_reviewer_decisions_hidden_initially": True,
            "sealed_cases_used": False,
            "candidate_order_not_changed_during_adjudication": True,
        }
        for key, expected_value in expected.items():
            if attestation.get(key) is not expected_value:
                blockers.append(f"precedence review attestation failed: {key}")

    complete = not blockers
    accepted = complete and adjudicated == "ACCEPT"
    return PrecedenceReviewReadiness(
        complete=complete,
        accepted=accepted,
        initial_agreement=initial_agreement,
        blockers=tuple(sorted(set(blockers))),
    )
