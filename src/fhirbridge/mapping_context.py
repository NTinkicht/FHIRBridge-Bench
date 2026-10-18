"""Build the frozen mapping context consumed by mapping-aware LLM arms."""

from __future__ import annotations

import json
from typing import Any

_REQUIRED_PROFILE_TRUE_PATHS = (
    ("identity_verification", "profile_identity_guard_passed"),
    ("identity_verification", "edition_5_evidence_checked"),
    ("identity_verification", "errata_2024dec_evidence_checked"),
    ("identity_verification", "independent_profile_provenance_reviewed"),
    ("qualification", "local_reference_messages_passed"),
    ("qualification", "structural_negative_controls_passed"),
    ("qualification", "warning_error_policy_frozen"),
)

_RULE_KEYS = (
    "rule_id",
    "canonical_fact",
    "projectability",
    "source_paths",
    "target_paths",
    "allowed_operations",
    "equivalence",
    "applies_when",
)

_GUARD_KEYS = (
    "guard_id",
    "source_fact_type",
    "additional_source_fact_types",
    "additional_source_relation_type",
    "source_field",
    "target_fact_type",
    "target_field",
    "match_type",
)


def _path_value(document: dict[str, Any], path: tuple[str, str]) -> Any:
    first = document.get(path[0])
    if not isinstance(first, dict):
        return None
    return first.get(path[1])


def _selected(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in keys if key in source}


def build_frozen_mapping_context(
    contract: dict[str, Any],
    status_mappings: dict[str, Any],
    specimen_bindings: dict[str, Any],
    profile_pin: dict[str, Any],
) -> dict[str, Any]:
    """Build confirmatory model context only from fully frozen artifacts."""

    contract_meta = contract.get("contract")
    if not isinstance(contract_meta, dict):
        raise ValueError("contract metadata is missing")
    if contract_meta.get("freeze_status") != "frozen":
        raise ValueError("projectability contract is not frozen")

    pin_meta = profile_pin.get("profile_pin")
    if not isinstance(pin_meta, dict) or pin_meta.get("status") != "frozen":
        raise ValueError("Edition 5 profile pin is not frozen")
    failed_profile_checks = [
        ".".join(path)
        for path in _REQUIRED_PROFILE_TRUE_PATHS
        if _path_value(profile_pin, path) is not True
    ]
    if failed_profile_checks:
        raise ValueError(
            "Edition 5 profile qualification is incomplete: "
            + ", ".join(failed_profile_checks)
        )

    status_meta = status_mappings.get("status_mapping_candidates")
    if not isinstance(status_meta, dict) or status_meta.get("status") != "frozen":
        raise ValueError("status mapping artifact is not frozen")

    specimen_meta = specimen_bindings.get("specimen_binding_candidates")
    if (
        not isinstance(specimen_meta, dict)
        or specimen_meta.get("status") != "frozen"
    ):
        raise ValueError("specimen binding artifact is not frozen")

    rules = contract.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("contract rules are missing")

    included_rules: list[dict[str, Any]] = []
    excluded_rule_ids: list[str] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("contract contains a malformed rule")
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("contract rule_id is missing")
        projectability = rule.get("projectability")
        if projectability == "INDETERMINATE":
            excluded_rule_ids.append(rule_id)
            continue
        if rule.get("status") != "frozen":
            raise ValueError(f"determinate rule is not frozen: {rule_id}")
        included_rules.append(_selected(rule, _RULE_KEYS))

    guards = contract.get("grounding_guards", [])
    if not isinstance(guards, list):
        raise ValueError("grounding_guards must be a list")
    included_guards: list[dict[str, Any]] = []
    for guard in guards:
        if not isinstance(guard, dict):
            raise ValueError("contract contains a malformed grounding guard")
        guard_id = guard.get("guard_id")
        if guard.get("status") != "frozen":
            raise ValueError(f"grounding guard is not frozen: {guard_id}")
        included_guards.append(_selected(guard, _GUARD_KEYS))

    report_map = status_mappings.get("diagnostic_report_to_obr25", {})
    observation_map = status_mappings.get("observation_to_obx11", {})
    specimen_projection = specimen_bindings.get(
        "candidate_projection_after_binding_review",
        {},
    )
    if not all(
        isinstance(value, dict)
        for value in (report_map, observation_map, specimen_projection)
    ):
        raise ValueError("frozen mapping artifacts are malformed")

    context = {
        "context_id": "FHIRBRIDGE-FROZEN-MAPPING-CONTEXT-001",
        "contract": {
            "id": contract_meta.get("id"),
            "version": contract_meta.get("version"),
        },
        "target": {
            "profile": profile_pin.get("target", {}).get(
                "selected_precoordinated_profile"
            ),
            "edition": profile_pin.get("target", {}).get(
                "implementation_guide_edition"
            ),
            "errata": profile_pin.get("target", {}).get("errata"),
        },
        "rules": included_rules,
        "grounding_guards": included_guards,
        "status_maps": {
            "diagnostic_report_status_to_OBR_25": report_map.get(
                "safe_unique_inverse",
                {},
            ),
            "observation_status_to_OBX_11": observation_map.get(
                "safe_unique_inverse",
                {},
            ),
        },
        "specimen_maps": {
            "serum_to_SPM_4": specimen_projection.get("serum_to_SPM_4"),
            "venipuncture_to_SPM_7": specimen_projection.get(
                "venipuncture_to_SPM_7"
            ),
        },
        "excluded_indeterminate_rule_ids": sorted(excluded_rule_ids),
        "policy": {
            "indeterminate_rules_must_not_be_used": True,
            "source_grounding_required": True,
            "invent_missing_business_facts": False,
        },
    }
    return context


def mapping_context_json(context: dict[str, Any]) -> str:
    """Canonical JSON representation used as the prompt artifact."""

    return json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
