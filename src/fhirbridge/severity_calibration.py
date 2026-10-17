"""Readiness checks for expert calibration of the semantic severity rubric."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

_REQUIRED_ANCHOR_ROLES = frozenset(
    {
        "S1_S2_boundary",
        "S2_S3_boundary",
        "clear_S2_anchor",
        "clear_S3_anchor",
    }
)
_THRESHOLD_LEVELS = {
    "S1_or_higher": ["S1", "S2", "S3"],
    "S2_or_higher": ["S2", "S3"],
    "S3_only": ["S3"],
}
_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class SeverityCalibrationReadiness:
    ready: bool
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


def assess_severity_calibration(
    document: dict[str, Any],
) -> SeverityCalibrationReadiness:
    blockers: list[str] = []

    if document.get("status") != "completed":
        blockers.append("severity calibration is not marked completed")
    if document.get("created_at") is None:
        blockers.append("severity calibration has no completion timestamp")
    if _placeholder(document.get("calibration_id")):
        blockers.append("severity calibration_id is still a placeholder")
    if not _sha256(document.get("candidate_policy_sha256")):
        blockers.append("candidate severity-policy SHA-256 is not frozen")

    blind = document.get("blind_stage_evidence")
    if not isinstance(blind, dict):
        blockers.append("blind severity-stage evidence is missing")
    else:
        if blind.get("assignment_id") != "FHIRBRIDGE-SEVERITY-BLIND-001":
            blockers.append("blind severity assignment_id is invalid")
        for key in (
            "reviewer_a_response_sha256",
            "reviewer_b_response_sha256",
        ):
            if not _sha256(blind.get(key)):
                blockers.append(f"{key} is not a frozen SHA-256")
        if blind.get("original_responses_retained") is not True:
            blockers.append("blind severity responses are not attested as retained")
        if blind.get("boundary_roles_hidden_initially") is not True:
            blockers.append("severity boundary roles were not hidden initially")

    reviewers = document.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        blockers.append("at least two severity-calibration reviewers are required")
        reviewers = []

    reviewer_ids: set[str] = set()
    for reviewer in reviewers:
        if not isinstance(reviewer, dict):
            blockers.append("severity calibration reviewer entry is malformed")
            continue
        reviewer_id = reviewer.get("reviewer_id")
        if (
            not isinstance(reviewer_id, str)
            or not reviewer_id
            or _placeholder(reviewer_id)
        ):
            blockers.append("severity calibration reviewer_id is incomplete")
            continue
        if reviewer_id in reviewer_ids:
            blockers.append(f"duplicate severity reviewer_id: {reviewer_id}")
        reviewer_ids.add(reviewer_id)
        expertise = reviewer.get("expertise")
        if (
            not isinstance(expertise, list)
            or not expertise
            or any(
                not isinstance(value, str)
                or not value
                or _placeholder(value)
                for value in expertise
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

    anchors = document.get("anchor_reviews")
    if not isinstance(anchors, list) or len(anchors) < 4:
        blockers.append("at least four severity anchor reviews are required")
        anchors = []

    anchor_ids: set[str] = set()
    observed_roles: set[str] = set()
    computed_disagreements: set[str] = set()
    exact_count = 0

    for anchor in anchors:
        if not isinstance(anchor, dict):
            blockers.append("severity anchor review is malformed")
            continue
        anchor_id = anchor.get("anchor_id")
        if (
            not isinstance(anchor_id, str)
            or not anchor_id
            or _placeholder(anchor_id)
        ):
            blockers.append("severity anchor_id is incomplete")
            continue
        if anchor_id in anchor_ids:
            blockers.append(f"duplicate severity anchor_id: {anchor_id}")
        anchor_ids.add(anchor_id)

        role = anchor.get("expected_boundary_role")
        if isinstance(role, str):
            observed_roles.add(role)

        description = anchor.get("anchor_description")
        if (
            not isinstance(description, str)
            or not description.strip()
            or _placeholder(description)
        ):
            blockers.append(f"{anchor_id}: anchor description is incomplete")

        ratings = anchor.get("reviewer_ratings")
        if not isinstance(ratings, list):
            blockers.append(f"{anchor_id}: reviewer_ratings are missing")
            continue

        rating_by_reviewer: dict[str, str] = {}
        for rating in ratings:
            if not isinstance(rating, dict):
                blockers.append(f"{anchor_id}: reviewer rating is malformed")
                continue
            reviewer_id = rating.get("reviewer_id")
            severity = rating.get("severity")
            rationale = rating.get("rationale")
            if not isinstance(reviewer_id, str) or not reviewer_id:
                blockers.append(f"{anchor_id}: reviewer rating lacks reviewer_id")
                continue
            if reviewer_id in rating_by_reviewer:
                blockers.append(
                    f"{anchor_id}: duplicate rating by reviewer {reviewer_id}"
                )
            if not isinstance(severity, str):
                blockers.append(f"{anchor_id}: severity rating is missing")
                continue
            rating_by_reviewer[reviewer_id] = severity
            if (
                not isinstance(rationale, str)
                or not rationale.strip()
                or _placeholder(rationale)
            ):
                blockers.append(
                    f"{anchor_id}: reviewer rationale is incomplete"
                )

        if set(rating_by_reviewer) != reviewer_ids:
            blockers.append(
                f"{anchor_id}: reviewer ratings do not match calibration roster"
            )
        elif len(set(rating_by_reviewer.values())) == 1:
            exact_count += 1
        else:
            computed_disagreements.add(anchor_id)

        adjudicated = anchor.get("adjudicated_severity")
        if adjudicated == "INDETERMINATE":
            blockers.append(
                f"{anchor_id}: completed calibration cannot retain "
                "INDETERMINATE adjudicated severity"
            )
        rationale = anchor.get("adjudication_rationale")
        if (
            not isinstance(rationale, str)
            or not rationale.strip()
            or _placeholder(rationale)
        ):
            blockers.append(
                f"{anchor_id}: adjudication rationale is incomplete"
            )

    missing_roles = _REQUIRED_ANCHOR_ROLES - observed_roles
    if missing_roles:
        blockers.append(
            "severity calibration lacks required anchor roles: "
            + ", ".join(sorted(missing_roles))
        )

    agreement = document.get("pre_adjudication_agreement")
    if not isinstance(agreement, dict):
        blockers.append("pre-adjudication severity agreement is missing")
    elif anchors:
        anchor_count = len(anchors)
        if agreement.get("anchor_count") != anchor_count:
            blockers.append("severity agreement anchor_count is inconsistent")
        if agreement.get("exact_agreement_count") != exact_count:
            blockers.append(
                "severity exact_agreement_count is inconsistent with ratings"
            )
        expected_rate = exact_count / anchor_count
        rate = agreement.get("exact_agreement_rate")
        if (
            not isinstance(rate, (int, float))
            or not math.isclose(
                float(rate),
                expected_rate,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            blockers.append(
                "severity exact_agreement_rate is inconsistent with ratings"
            )
        recorded_disagreements = agreement.get("disagreement_anchor_ids")
        if not isinstance(recorded_disagreements, list) or set(
            recorded_disagreements
        ) != computed_disagreements:
            blockers.append(
                "severity disagreement_anchor_ids do not match initial ratings"
            )

    decision = document.get("major_threshold_decision")
    if not isinstance(decision, dict):
        blockers.append("major severity threshold decision is missing")
    else:
        threshold = decision.get("threshold")
        expected_levels = _THRESHOLD_LEVELS.get(str(threshold))
        if expected_levels is None:
            blockers.append("major severity threshold is unsupported")
        elif decision.get("included_levels") != expected_levels:
            blockers.append(
                "major threshold included_levels do not match threshold"
            )
        if decision.get("decision_status") != (
            "frozen_for_confirmatory_endpoint"
        ):
            blockers.append("major severity threshold is not frozen")
        rationale = decision.get("rationale")
        if (
            not isinstance(rationale, str)
            or not rationale.strip()
            or _placeholder(rationale)
        ):
            blockers.append("major severity threshold rationale is incomplete")

    attestation = document.get("attestation")
    if not isinstance(attestation, dict):
        blockers.append("severity calibration attestation is missing")
    else:
        expected = {
            "independent_initial_ratings": True,
            "sealed_cases_used": False,
            "adjudication_after_initial_ratings": True,
            "all_disagreements_retained": True,
        }
        for key, expected_value in expected.items():
            if attestation.get(key) is not expected_value:
                blockers.append(
                    f"severity calibration attestation failed: {key}"
                )

    return SeverityCalibrationReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
