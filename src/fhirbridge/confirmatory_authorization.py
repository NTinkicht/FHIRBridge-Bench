"""Fail-closed authorization for starting confirmatory model inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .analysis_preregistration import assess_analysis_preregistration
from .expert_assignments import assess_case_assignment_manifest
from .expert_roles import assess_reviewer_roster
from .freeze_audit import assess_presealed_freeze
from .model_config_readiness import assess_model_prompt_freeze
from .pilot_acceptance import assess_pilot_acceptance_preregistration
from .sample_size_readiness import assess_sample_size_preregistration
from .tooling_manifest import assess_freeze_readiness

_REQUIRED_PROTOCOL_GATE_IDS = frozenset(
    {
        "order_context_end_to_end",
        "required_element_inventory",
        "external_contract_review",
        "renderer_b_clean_room",
        "status_and_code_maps",
        "measurement_error_policy",
        "primary_metric_definition",
        "per_scenario_feasibility",
        "pilot_acceptance_gate",
        "sample_size_preregistration",
        "model_prompt_configuration",
        "sealed_expert_validation",
    }
)

_REQUIRED_BOUND_HASHES = {
    "instrument_component_manifest": (
        "instrument_component_manifest",
        "sha256",
    ),
    "sealed_case_manifest": ("sealed_set", "case_manifest_sha256"),
    "reviewer_roster": ("reviewer_roster", "sha256"),
    "case_assignment_manifest": ("case_assignment_manifest", "sha256"),
    "analysis_preregistration": ("analysis_preregistration", "sha256"),
    "sample_size_preregistration": (
        "sample_size_preregistration",
        "sha256",
    ),
    "model_prompt_configuration": ("model_prompt_configuration", "sha256"),
    "pilot_acceptance_preregistration": (
        "acceptance_gate",
        "preregistration_sha256",
    ),
}


@dataclass(frozen=True)
class ConfirmatoryAuthorization:
    authorized: bool
    blockers: tuple[str, ...]


def _protocol_blockers(document: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    freeze = document.get("protocol_freeze")
    if not isinstance(freeze, dict):
        return ["protocol_freeze metadata is missing"]
    if freeze.get("status") != "frozen":
        blockers.append("protocol freeze status is not frozen")

    gates = document.get("gates")
    if not isinstance(gates, list) or not gates:
        blockers.append("protocol freeze gate ledger is missing")
        return blockers

    seen_ids: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            blockers.append("protocol gate entry is malformed")
            continue
        gate_id = gate.get("gate_id")
        if not isinstance(gate_id, str) or not gate_id:
            blockers.append("protocol gate entry lacks gate_id")
            continue
        if gate_id in seen_ids:
            blockers.append(f"duplicate protocol gate_id: {gate_id}")
        seen_ids.add(gate_id)
        if gate.get("status") != "passed":
            blockers.append(f"protocol gate is not passed: {gate_id}")
        residual = gate.get("blockers", [])
        if residual not in ([], None):
            blockers.append(
                f"protocol gate still lists blocker items: {gate_id}"
            )

    missing_gate_ids = _REQUIRED_PROTOCOL_GATE_IDS - seen_ids
    unexpected_gate_ids = seen_ids - _REQUIRED_PROTOCOL_GATE_IDS
    if missing_gate_ids:
        blockers.append(
            "protocol gate ledger is missing required gates: "
            + ", ".join(sorted(missing_gate_ids))
        )
    if unexpected_gate_ids:
        blockers.append(
            "protocol gate ledger contains unexpected gates: "
            + ", ".join(sorted(unexpected_gate_ids))
        )

    policy = document.get("confirmatory_run_policy")
    if not isinstance(policy, dict):
        blockers.append("confirmatory_run_policy is missing")
    else:
        if policy.get("allowed_when_all_protocol_gates_passed") is not True:
            blockers.append("confirmatory run policy does not permit ready runs")
        if policy.get("tooling_manifest_must_also_be_frozen") is not True:
            blockers.append("confirmatory run policy does not require frozen tooling")
        if policy.get("no_confirmatory_model_inference_before_ready") is not True:
            blockers.append("confirmatory run policy lacks pre-readiness prohibition")
    return blockers


def _bound_hash(
    freeze_manifest: dict[str, Any],
    path: tuple[str, str],
) -> str | None:
    parent = freeze_manifest.get(path[0])
    if not isinstance(parent, dict):
        return None
    value = parent.get(path[1])
    return value if isinstance(value, str) else None


def assess_confirmatory_authorization(
    *,
    protocol_gates: dict[str, Any],
    tooling_manifest: dict[str, Any],
    freeze_manifest: dict[str, Any],
    reviewer_roster: dict[str, Any],
    case_assignment_manifest: dict[str, Any],
    analysis_preregistration: dict[str, Any],
    sample_size_preregistration: dict[str, Any],
    model_prompt_configuration: dict[str, Any],
    pilot_acceptance_preregistration: dict[str, Any],
    actual_artifact_sha256: dict[str, str],
    actual_component_sha256: dict[str, str],
    sealed_case_ids: set[str],
    actual_repository_commit: str,
) -> ConfirmatoryAuthorization:
    """Authorize confirmatory inference only when every frozen gate agrees."""

    blockers: list[str] = []
    blockers.extend(_protocol_blockers(protocol_gates))

    frozen_repository_commit = freeze_manifest.get("repository_commit")
    if (
        not isinstance(actual_repository_commit, str)
        or len(actual_repository_commit) < 7
        or len(actual_repository_commit) > 40
        or any(
            ch not in "0123456789abcdefABCDEF"
            for ch in actual_repository_commit
        )
    ):
        blockers.append("actual repository commit is missing or malformed")
    elif frozen_repository_commit != actual_repository_commit.lower():
        blockers.append(
            "actual repository commit does not match freeze manifest"
        )

    tooling = assess_freeze_readiness(tooling_manifest)
    if not tooling.ready:
        blockers.extend(
            f"tooling freeze unresolved: {path}"
            for path in tooling.unresolved_paths
        )
        blockers.extend(
            f"tooling qualification flag is not true: {path}"
            for path in tooling.false_boolean_paths
        )
    if tooling.manifest_status != "frozen":
        blockers.append("tooling manifest status is not frozen")

    presealed = assess_presealed_freeze(freeze_manifest)
    blockers.extend(
        f"sealed freeze audit: {reason}" for reason in presealed.blockers
    )

    roster = assess_reviewer_roster(reviewer_roster)
    blockers.extend(
        f"reviewer roster: {reason}" for reason in roster.blockers
    )

    assignments = assess_case_assignment_manifest(
        case_assignment_manifest,
        reviewer_roster,
        expected_case_ids=sealed_case_ids,
    )
    blockers.extend(
        f"case assignment: {reason}" for reason in assignments.blockers
    )

    analysis = assess_analysis_preregistration(analysis_preregistration)
    blockers.extend(
        f"analysis preregistration: {reason}" for reason in analysis.blockers
    )

    sample_size = assess_sample_size_preregistration(
        sample_size_preregistration
    )
    blockers.extend(
        f"sample-size preregistration: {reason}"
        for reason in sample_size.blockers
    )

    model_config = assess_model_prompt_freeze(model_prompt_configuration)
    blockers.extend(
        f"model/prompt freeze: {reason}" for reason in model_config.blockers
    )

    pilot = assess_pilot_acceptance_preregistration(
        pilot_acceptance_preregistration
    )
    blockers.extend(
        f"pilot acceptance: {reason}" for reason in pilot.blockers
    )

    for key, freeze_path in _REQUIRED_BOUND_HASHES.items():
        actual = actual_artifact_sha256.get(key)
        expected = _bound_hash(freeze_manifest, freeze_path)
        if not isinstance(actual, str) or len(actual) != 64:
            blockers.append(f"actual artifact SHA-256 is missing: {key}")
            continue
        if expected != actual:
            blockers.append(
                f"freeze-manifest SHA-256 mismatch for {key}"
            )

    frozen_components = freeze_manifest.get("instrument_components")
    if not isinstance(frozen_components, dict):
        blockers.append("freeze manifest instrument_components are missing")
        frozen_components = {}
    frozen_component_names = set(frozen_components)
    actual_component_names = set(actual_component_sha256)
    missing_component_hashes = frozen_component_names - actual_component_names
    unexpected_component_hashes = actual_component_names - frozen_component_names
    if missing_component_hashes:
        blockers.append(
            "actual component digest set is missing frozen components: "
            + ", ".join(sorted(missing_component_hashes))
        )
    if unexpected_component_hashes:
        blockers.append(
            "actual component digest set contains unfrozen components: "
            + ", ".join(sorted(unexpected_component_hashes))
        )

    for component_name, component in sorted(frozen_components.items()):
        if not isinstance(component, dict):
            blockers.append(
                f"freeze manifest component is malformed: {component_name}"
            )
            continue
        expected = component.get("sha256")
        actual = actual_component_sha256.get(component_name)
        if not isinstance(actual, str) or len(actual) != 64:
            blockers.append(
                f"actual component SHA-256 is missing: {component_name}"
            )
            continue
        if expected != actual:
            blockers.append(
                f"freeze-manifest component SHA-256 mismatch for "
                f"{component_name}"
            )

    if not sealed_case_ids:
        blockers.append("sealed case ID set must not be empty")
    else:
        sealed = freeze_manifest.get("sealed_set")
        if isinstance(sealed, dict):
            case_count = sealed.get("case_count")
            if case_count != len(sealed_case_ids):
                blockers.append(
                    "sealed case ID count does not match freeze manifest"
                )

    return ConfirmatoryAuthorization(
        authorized=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
