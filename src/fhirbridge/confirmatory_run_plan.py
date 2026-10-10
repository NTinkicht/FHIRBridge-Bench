"""Readiness checks for the pre-inference confirmatory run plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class ConfirmatoryRunPlanReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zeroish(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and set(value.lower()) <= {"0"}


def assess_confirmatory_run_plan(
    document: dict[str, Any],
) -> ConfirmatoryRunPlanReadiness:
    blockers: list[str] = []

    if document.get("status") != "prepared_authorized":
        blockers.append("confirmatory run plan is not prepared_authorized")
    if document.get("created_at") is None:
        blockers.append("confirmatory run plan has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened at run-plan freeze")
    if document.get("inference_started") is not False:
        blockers.append("inference must not have started at run-plan freeze")
    if _placeholder(document.get("run_plan_id")):
        blockers.append("run_plan_id is still a placeholder")
    if _zeroish(document.get("repository_commit")):
        blockers.append("repository_commit is still a zero placeholder")

    authorization = document.get("authorization")
    if not isinstance(authorization, dict):
        blockers.append("authorization record is missing")
    else:
        if authorization.get("authorized") is not True:
            blockers.append("run authorization is not true")
        if _zeroish(authorization.get("record_sha256")):
            blockers.append("authorization record SHA-256 is still a zero placeholder")

    frozen = document.get("frozen_artifacts")
    if not isinstance(frozen, dict):
        blockers.append("frozen_artifacts are missing")
        frozen = {}
    for key in (
        "freeze_manifest_sha256",
        "protocol_freeze_gates_sha256",
        "tooling_manifest_sha256",
        "model_prompt_configuration_sha256",
        "analysis_preregistration_sha256",
        "sample_size_preregistration_sha256",
        "pilot_acceptance_preregistration_sha256",
        "execution_record_schema_sha256",
    ):
        value = frozen.get(key)
        if not isinstance(value, str) or len(value) != 64 or _zeroish(value):
            blockers.append(f"{key} is missing or still a zero placeholder")

    execution_contract = document.get("execution_record_contract")
    if not isinstance(execution_contract, dict):
        blockers.append("execution_record_contract is missing")
    else:
        if execution_contract.get("schema_version") != "0.3.0":
            blockers.append(
                "execution record schema_version is not frozen to 0.3.0"
            )
        expected_bindings = [
            "model_prompt_freeze_sha256",
            "source_input_sha256",
            "rendered_prompt_sha256",
            "mapping_context_sha256",
        ]
        if execution_contract.get("required_bindings") != expected_bindings:
            blockers.append(
                "execution record required_bindings do not match frozen lineage policy"
            )
        if execution_contract.get("mapping_repair_lineage_required") is not True:
            blockers.append(
                "mapping-to-repair execution lineage is not required"
            )
        if execution_contract.get("schema_validation_required") is not True:
            blockers.append(
                "execution-record schema validation is not required"
            )

    sealed = document.get("sealed_set")
    if not isinstance(sealed, dict):
        blockers.append("sealed_set binding is missing")
        sealed = {}
    bundle_id = sealed.get("bundle_id")
    if not isinstance(bundle_id, str) or not bundle_id or _placeholder(bundle_id):
        blockers.append("sealed_set.bundle_id is missing or placeholder")
    for key in ("bundle_sha256", "case_manifest_sha256"):
        value = sealed.get(key)
        if not isinstance(value, str) or len(value) != 64 or _zeroish(value):
            blockers.append(f"sealed_set.{key} is missing or placeholder")
    case_count = sealed.get("case_count")
    if not isinstance(case_count, int) or isinstance(case_count, bool) or case_count < 1:
        blockers.append("sealed_set.case_count must be a positive integer")

    model_keys = document.get("model_keys")
    if not isinstance(model_keys, list) or not model_keys:
        blockers.append("model_keys must be a non-empty list")
        model_keys = []
    normalized: list[str] = []
    for model_key in model_keys:
        if (
            not isinstance(model_key, str)
            or not model_key
            or _placeholder(model_key)
        ):
            blockers.append("model_keys contain missing or placeholder values")
            continue
        if model_key in normalized:
            blockers.append(f"duplicate model_key: {model_key}")
        normalized.append(model_key)

    counts = document.get("expected_execution_counts")
    if not isinstance(counts, dict):
        blockers.append("expected_execution_counts are missing")
        counts = {}

    if (
        isinstance(case_count, int)
        and case_count > 0
        and normalized
    ):
        model_count = len(normalized)
        expected = {
            "provider_generation_calls": case_count * model_count * 2,
            "derived_repair_outputs": case_count * model_count,
            "deterministic_baseline_outputs": case_count,
            "total_arm_outputs": case_count * (1 + 3 * model_count),
        }
        for key, value in expected.items():
            if counts.get(key) != value:
                blockers.append(
                    f"expected_execution_counts.{key} does not match frozen design"
                )

    return ConfirmatoryRunPlanReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
