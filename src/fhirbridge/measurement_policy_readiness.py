"""Consistency and freeze-readiness checks for semantic error policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXPECTED_LEVELS = ("S0", "S1", "S2", "S3")
_EXPECTED_PRECEDENCE = (
    "MISATTRIBUTION",
    "CORRUPTION",
    "OMISSION",
    "FABRICATION",
)


@dataclass(frozen=True)
class MeasurementPolicyReadiness:
    consistent: bool
    freeze_ready: bool
    consistency_blockers: tuple[str, ...]
    freeze_blockers: tuple[str, ...]


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
        and set(value.lower()) != {"0"}
    )


def assess_measurement_policies(
    contract: dict[str, Any],
    fault_taxonomy: dict[str, Any],
    severity_policy: dict[str, Any],
    precedence_policy: dict[str, Any],
) -> MeasurementPolicyReadiness:
    consistency: list[str] = []
    freeze: list[str] = []

    levels = severity_policy.get("levels")
    if not isinstance(levels, dict):
        consistency.append("severity policy levels are missing")
        level_ids: set[str] = set()
    else:
        level_ids = set(levels)
        if tuple(levels) != _EXPECTED_LEVELS:
            consistency.append(
                "severity levels must be ordered exactly S0, S1, S2, S3"
            )
        for level_id in _EXPECTED_LEVELS:
            level = levels.get(level_id)
            if not isinstance(level, dict):
                consistency.append(f"severity level {level_id} is missing")
                continue
            definition = level.get("definition")
            if not isinstance(definition, str) or not definition.strip():
                consistency.append(
                    f"severity level {level_id} lacks a definition"
                )

    rules = contract.get("rules")
    if not isinstance(rules, list):
        consistency.append("contract rules are missing")
        rules = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        severity = rule.get("severity_default")
        if severity not in level_ids:
            consistency.append(
                f"contract rule {rule.get('rule_id')} has undefined "
                f"severity_default {severity!r}"
            )

    fault_classes = fault_taxonomy.get("fault_classes")
    if not isinstance(fault_classes, list):
        consistency.append("fault taxonomy classes are missing")
        fault_classes = []
    for fault in fault_classes:
        if not isinstance(fault, dict):
            continue
        severity = fault.get("default_severity")
        if severity not in level_ids:
            consistency.append(
                f"fault {fault.get('id')} has undefined "
                f"default_severity {severity!r}"
            )

    contract_precedence = contract.get("precedence")
    if not isinstance(contract_precedence, dict):
        consistency.append("contract precedence is missing")
        contract_order: tuple[str, ...] = ()
    else:
        raw = contract_precedence.get("order")
        contract_order = tuple(raw) if isinstance(raw, list) else ()

    taxonomy_raw = fault_taxonomy.get("precedence")
    taxonomy_order = (
        tuple(taxonomy_raw) if isinstance(taxonomy_raw, list) else ()
    )
    policy_header = precedence_policy.get("precedence_policy")
    if not isinstance(policy_header, dict):
        consistency.append("precedence policy metadata is missing")
        policy_header = {}
    policy_raw = precedence_policy.get("order")
    policy_order = tuple(policy_raw) if isinstance(policy_raw, list) else ()

    if contract_order != _EXPECTED_PRECEDENCE:
        consistency.append("contract precedence differs from frozen candidate")
    if taxonomy_order != _EXPECTED_PRECEDENCE:
        consistency.append("fault taxonomy precedence differs from candidate")
    if policy_order != _EXPECTED_PRECEDENCE:
        consistency.append("standalone precedence candidate has wrong order")
    if len(set(policy_order)) != len(policy_order):
        consistency.append("precedence order contains duplicate classes")

    major = severity_policy.get("primary_endpoint_major_candidate")
    if not isinstance(major, dict):
        consistency.append("primary endpoint major candidate is missing")
        major = {}
    major_levels = major.get("levels")
    if major_levels != ["S2", "S3"]:
        consistency.append(
            "current major endpoint candidate must be exactly S2 and S3"
        )
    elif not set(major_levels).issubset(level_ids):
        consistency.append("major endpoint candidate uses undefined severity")

    severity_header = severity_policy.get("severity_policy")
    if not isinstance(severity_header, dict):
        freeze.append("severity policy metadata is missing")
        severity_header = {}
    if severity_header.get("status") != "frozen":
        freeze.append("severity policy status is not frozen")
    if major.get("status") != "frozen":
        freeze.append("primary endpoint major threshold is not frozen")

    calibration = severity_policy.get("expert_calibration")
    if not isinstance(calibration, dict):
        freeze.append("severity expert calibration evidence is missing")
    else:
        if calibration.get("status") != "completed":
            freeze.append("severity expert calibration is not completed")
        if not isinstance(calibration.get("record_ref"), str) or not calibration.get(
            "record_ref"
        ):
            freeze.append("severity calibration record_ref is missing")
        if not _sha256(calibration.get("record_sha256")):
            freeze.append("severity calibration record SHA-256 is not frozen")

    if policy_header.get("status") != "frozen":
        freeze.append("error precedence policy status is not frozen")

    consistent = not consistency
    freeze_ready = consistent and not freeze
    return MeasurementPolicyReadiness(
        consistent=consistent,
        freeze_ready=freeze_ready,
        consistency_blockers=tuple(sorted(set(consistency))),
        freeze_blockers=tuple(sorted(set(freeze))),
    )
