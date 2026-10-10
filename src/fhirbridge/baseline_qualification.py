"""Fail-closed readiness checks for deterministic baseline qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXPECTED_FAMILIES = frozenset(f"LAB-{index:03d}" for index in range(1, 12))
_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class BaselineQualificationReadiness:
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
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
        and set(value.lower()) != {"0"}
    )


def assess_baseline_qualification(
    document: dict[str, Any],
) -> BaselineQualificationReadiness:
    blockers: list[str] = []

    if document.get("status") != "qualified":
        blockers.append("baseline qualification is not marked qualified")
    if document.get("created_at") is None:
        blockers.append("baseline qualification has no completion timestamp")
    if _placeholder(document.get("qualification_id")):
        blockers.append("baseline qualification_id is still a placeholder")

    commit = document.get("repository_commit")
    if (
        not isinstance(commit, str)
        or len(commit) < 7
        or set(commit.lower()) <= {"0"}
    ):
        blockers.append("baseline repository_commit is missing or placeholder")

    contract = document.get("contract")
    if not isinstance(contract, dict):
        blockers.append("baseline contract evidence is missing")
    else:
        if contract.get("freeze_status") != "frozen":
            blockers.append("baseline contract is not frozen")
        if not _sha256(contract.get("sha256")):
            blockers.append("baseline contract SHA-256 is not frozen")

    profile = document.get("target_profile")
    if not isinstance(profile, dict):
        blockers.append("baseline target profile evidence is missing")
    else:
        if profile.get("name") != "LRI_NG_FRU_Profile_V3":
            blockers.append("baseline target profile is not LRI_NG_FRU_Profile_V3")
        for key in ("profile_bundle_sha256", "qualification_report_sha256"):
            if not _sha256(profile.get(key)):
                blockers.append(f"baseline {key} is not frozen")

    renderer = document.get("renderer_component")
    if not isinstance(renderer, dict):
        blockers.append("baseline renderer component evidence is missing")
    else:
        if renderer.get("component_name") != "deterministic_baseline_renderer":
            blockers.append("baseline renderer component name is invalid")
        if not _sha256(renderer.get("sha256")):
            blockers.append("baseline renderer component SHA-256 is not frozen")

    evidence = document.get("primary_family_evidence")
    if not isinstance(evidence, list):
        blockers.append("baseline primary-family evidence is missing")
        evidence = []

    seen: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            blockers.append("baseline family evidence contains malformed item")
            continue
        template_id = item.get("template_id")
        if not isinstance(template_id, str):
            blockers.append("baseline family evidence lacks template_id")
            continue
        if template_id in seen:
            blockers.append(f"duplicate baseline family evidence: {template_id}")
        seen.add(template_id)
        if item.get("order_context_present") is not True:
            blockers.append(f"{template_id}: order context is not attested")
        if item.get("structural_validity") != "VALID":
            blockers.append(f"{template_id}: structural validity is not VALID")
        if item.get("semantic_verdict") != "FAITHFUL":
            blockers.append(f"{template_id}: semantic verdict is not FAITHFUL")
        if not _sha256(item.get("validation_record_sha256")):
            blockers.append(
                f"{template_id}: validation record SHA-256 is not frozen"
            )

    missing = _EXPECTED_FAMILIES - seen
    extra = seen - _EXPECTED_FAMILIES
    if missing:
        blockers.append(
            "baseline qualification is missing primary families: "
            + ", ".join(sorted(missing))
        )
    if extra:
        blockers.append(
            "baseline qualification contains non-primary families: "
            + ", ".join(sorted(extra))
        )

    aggregate = document.get("aggregate")
    if not isinstance(aggregate, dict):
        blockers.append("baseline aggregate evidence is missing")
    else:
        expected = {
            "primary_family_count": 11,
            "all_primary_families_structurally_valid": True,
            "all_primary_families_semantically_faithful": True,
            "order_context_supported": True,
            "exact_profile_validation_used": True,
        }
        for key, expected_value in expected.items():
            if aggregate.get(key) != expected_value:
                blockers.append(f"baseline aggregate condition failed: {key}")

    attestation = document.get("attestation")
    if not isinstance(attestation, dict):
        blockers.append("baseline qualification attestation is missing")
    else:
        for key in (
            "no_invented_business_facts",
            "development_placeholder_codes_absent",
            "same_frozen_instrument_used_for_all_families",
            "confirmatory_model_outputs_not_used",
        ):
            if attestation.get(key) is not True:
                blockers.append(f"baseline qualification attestation failed: {key}")

    return BaselineQualificationReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
