"""Readiness checks for sealed expert-case assignments."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .expert_roles import assess_reviewer_roster

_PRIMARY_ROLES = frozenset(
    {
        "primary_reviewer_interoperability",
        "primary_reviewer_clinical_informatics",
    }
)
_REQUIRED_PAIR_EXPERTISE = frozenset(
    {
        "hl7v2_fhir_interoperability",
        "clinical_informatics_laboratory",
    }
)
_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class CaseAssignmentReadiness:
    ready: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zero_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= {"0"}


def assess_case_assignment_manifest(
    document: dict[str, Any],
    reviewer_roster: dict[str, Any],
    *,
    expected_case_ids: set[str] | None = None,
) -> CaseAssignmentReadiness:
    blockers: list[str] = []
    warnings: list[str] = []

    roster_readiness = assess_reviewer_roster(reviewer_roster)
    if not roster_readiness.ready:
        blockers.extend(
            f"reviewer roster not ready: {reason}"
            for reason in roster_readiness.blockers
        )

    if document.get("status") != "locked_preopening":
        blockers.append("case assignment manifest is not locked preopening")
    if document.get("created_at") is None:
        blockers.append("case assignment manifest has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened when assignments are locked")
    if _placeholder(document.get("assignment_id")):
        blockers.append("case assignment ID is still a placeholder")

    roster_id = reviewer_roster.get("roster_id")
    if document.get("reviewer_roster_id") != roster_id:
        blockers.append("case assignment roster ID does not match reviewer roster")
    if _zero_hash(document.get("reviewer_roster_sha256")):
        blockers.append("reviewer roster SHA-256 is still a zero placeholder")
    if _zero_hash(document.get("sealed_case_manifest_sha256")):
        blockers.append("sealed case-manifest SHA-256 is still a zero placeholder")

    members = reviewer_roster.get("members", [])
    member_by_id = {
        member.get("member_id"): member
        for member in members
        if isinstance(member, dict)
        and isinstance(member.get("member_id"), str)
    }
    primary_ids = {
        member_id
        for member_id, member in member_by_id.items()
        if _PRIMARY_ROLES.intersection(member.get("roles", []))
    }

    assignments = document.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        blockers.append("case assignment manifest has no assignments")
        assignments = []

    seen_cases: set[str] = set()
    assigned_case_ids: set[str] = set()
    reviewer_load: Counter[str] = Counter()

    for item in assignments:
        if not isinstance(item, dict):
            blockers.append("case assignment contains a malformed entry")
            continue
        case_id = item.get("case_id")
        reviewers = item.get("primary_reviewer_ids")
        if not isinstance(case_id, str) or not case_id:
            blockers.append("case assignment has a missing case_id")
            continue
        if _placeholder(case_id):
            blockers.append(f"{case_id}: case ID is still a placeholder")
        if case_id in seen_cases:
            blockers.append(f"duplicate case assignment: {case_id}")
        seen_cases.add(case_id)
        assigned_case_ids.add(case_id)

        if (
            not isinstance(reviewers, list)
            or len(reviewers) != 2
            or len(set(reviewers)) != 2
        ):
            blockers.append(
                f"{case_id}: exactly two distinct primary reviewers are required"
            )
            continue

        pair_expertise: set[str] = set()
        for reviewer_id in reviewers:
            if reviewer_id not in primary_ids:
                blockers.append(
                    f"{case_id}: reviewer {reviewer_id} is not an eligible primary reviewer"
                )
                continue
            reviewer_load[str(reviewer_id)] += 1
            member = member_by_id[str(reviewer_id)]
            pair_expertise.update(
                str(value) for value in member.get("expertise", [])
            )
        missing_expertise = _REQUIRED_PAIR_EXPERTISE - pair_expertise
        if missing_expertise:
            blockers.append(
                f"{case_id}: reviewer pair lacks required expertise: "
                + ", ".join(sorted(missing_expertise))
            )

    if expected_case_ids is not None:
        missing = expected_case_ids - assigned_case_ids
        extra = assigned_case_ids - expected_case_ids
        if missing:
            blockers.append(
                "sealed cases missing reviewer assignments: "
                + ", ".join(sorted(missing))
            )
        if extra:
            blockers.append(
                "assignments include unknown sealed cases: "
                + ", ".join(sorted(extra))
            )

    if reviewer_load:
        loads = list(reviewer_load.values())
        if max(loads) - min(loads) > 1:
            warnings.append(
                "primary reviewer assignment load differs by more than one case"
            )
        unassigned = primary_ids - set(reviewer_load)
        if unassigned:
            warnings.append(
                "eligible primary reviewers with zero assigned cases: "
                + ", ".join(sorted(unassigned))
            )

    return CaseAssignmentReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )
