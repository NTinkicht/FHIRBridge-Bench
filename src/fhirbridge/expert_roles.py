"""Fail-closed readiness checks for the sealed expert-review roster."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PRIMARY_ROLES = frozenset(
    {
        "primary_reviewer_interoperability",
        "primary_reviewer_clinical_informatics",
    }
)
_BLINDED_ACCESS_FIELDS = (
    "model_identity",
    "generation_strategy",
    "verifier_verdict",
    "claimed_provenance",
    "other_primary_reviewer_labels",
)
_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class ReviewerRosterReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def assess_reviewer_roster(document: dict[str, Any]) -> ReviewerRosterReadiness:
    blockers: list[str] = []

    if document.get("status") != "locked_preopening":
        blockers.append("reviewer roster is not locked preopening")
    if document.get("created_at") is None:
        blockers.append("reviewer roster has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened when roster is locked")
    if _placeholder(document.get("roster_id")):
        blockers.append("reviewer roster ID is still a placeholder")

    members = document.get("members")
    if not isinstance(members, list) or not members:
        return ReviewerRosterReadiness(
            ready=False,
            blockers=tuple(sorted(set(blockers + ["reviewer roster has no members"]))),
        )

    seen_ids: set[str] = set()
    primary_ids: set[str] = set()
    adjudicator_ids: set[str] = set()
    expertise_union: set[str] = set()
    primary_role_counts = {role: 0 for role in _PRIMARY_ROLES}

    for member in members:
        if not isinstance(member, dict):
            blockers.append("reviewer roster contains a malformed member")
            continue
        member_id = member.get("member_id")
        if not isinstance(member_id, str) or not member_id:
            blockers.append("reviewer member_id is missing")
            continue
        if member_id in seen_ids:
            blockers.append(f"duplicate reviewer member_id: {member_id}")
        seen_ids.add(member_id)
        if _placeholder(member_id):
            blockers.append(f"{member_id}: reviewer ID is still a placeholder")

        roles = member.get("roles", [])
        expertise = member.get("expertise", [])
        if not isinstance(roles, list):
            blockers.append(f"{member_id}: roles must be a list")
            roles = []
        if not isinstance(expertise, list):
            blockers.append(f"{member_id}: expertise must be a list")
            expertise = []

        is_primary = bool(_PRIMARY_ROLES.intersection(roles))
        if is_primary:
            primary_ids.add(member_id)
            expertise_union.update(str(value) for value in expertise)
            for role in _PRIMARY_ROLES:
                if role in roles:
                    primary_role_counts[role] += 1

            if member.get("renderer_implementation_participation") is not False:
                blockers.append(
                    f"{member_id}: primary reviewer participated in renderer implementation"
                )
            if (
                member.get("contract_review_participation") is True
                and member.get("analytical_separation_attested") is not True
            ):
                blockers.append(
                    f"{member_id}: contract-review overlap lacks analytical separation"
                )
            access = member.get("access")
            if not isinstance(access, dict):
                blockers.append(f"{member_id}: access profile is missing")
            else:
                for field in _BLINDED_ACCESS_FIELDS:
                    if access.get(field) is not False:
                        blockers.append(
                            f"{member_id}: primary reviewer has prohibited access to {field}"
                        )

        if "adjudicator" in roles:
            adjudicator_ids.add(member_id)

        for field in ("conflicts_of_interest", "prior_project_involvement"):
            value = member.get(field)
            if not isinstance(value, str) or not value.strip() or _placeholder(value):
                blockers.append(f"{member_id}: {field} disclosure is incomplete")

    if len(primary_ids) < 2:
        blockers.append("at least two distinct primary reviewers are required")
    for role, count in primary_role_counts.items():
        if count < 1:
            blockers.append(f"missing primary reviewer role: {role}")

    if "hl7v2_fhir_interoperability" not in expertise_union:
        blockers.append("primary reviewer pair lacks HL7 v2/FHIR expertise")
    if "clinical_informatics_laboratory" not in expertise_union:
        blockers.append("primary reviewer pair lacks laboratory clinical informatics expertise")

    if not adjudicator_ids:
        blockers.append("at least one adjudicator is required")
    if primary_ids.intersection(adjudicator_ids):
        blockers.append("adjudicator must be distinct from primary reviewers")

    return ReviewerRosterReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
