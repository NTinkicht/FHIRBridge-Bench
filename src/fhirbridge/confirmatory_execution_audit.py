"""Completeness and provenance audit for confirmatory execution records."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

_DIRECT = "direct_structured_llm"
_MAPPING = "mapping_aware_llm"
_REPAIR = "mapping_aware_plus_syntax_repair"
_RESPONSE = "RESPONSE_RECEIVED"
_UPSTREAM = "MEASUREMENT_FAILURE_UPSTREAM"
_POSTPROCESS = "MEASUREMENT_FAILURE_POSTPROCESSING"


@dataclass(frozen=True)
class ConfirmatoryExecutionAudit:
    complete: bool
    blockers: tuple[str, ...]
    provider_call_count: int
    derived_repair_count: int
    deterministic_baseline_count: int
    total_arm_output_count: int
    outcome_counts: dict[str, int]


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    case_id = record.get("case_id")
    model_key = record.get("model_key")
    strategy_id = record.get("strategy_id")
    if not all(
        isinstance(value, str) and value
        for value in (case_id, model_key, strategy_id)
    ):
        raise ValueError("execution record lacks case/model/strategy identity")
    return str(case_id), str(model_key), str(strategy_id)


def audit_confirmatory_execution(
    run_plan: dict[str, Any],
    llm_records: list[dict[str, Any]],
    *,
    sealed_case_ids: set[str],
    deterministic_baseline_case_ids: set[str],
) -> ConfirmatoryExecutionAudit:
    """Check exact run-plan coverage and repair provenance without imputing data."""

    blockers: list[str] = []
    if not sealed_case_ids:
        blockers.append("sealed_case_ids must not be empty")

    sealed = run_plan.get("sealed_set")
    if not isinstance(sealed, dict):
        blockers.append("run plan sealed_set binding is missing")
        sealed = {}
    if sealed.get("case_count") != len(sealed_case_ids):
        blockers.append("sealed case count does not match run plan")

    frozen_artifacts = run_plan.get("frozen_artifacts")
    if not isinstance(frozen_artifacts, dict):
        blockers.append("run plan frozen_artifacts are missing")
        frozen_artifacts = {}
    expected_model_freeze_hash = frozen_artifacts.get(
        "model_prompt_configuration_sha256"
    )
    if not _valid_sha256(expected_model_freeze_hash):
        blockers.append(
            "run plan model_prompt_configuration_sha256 is missing or invalid"
        )
        expected_model_freeze_hash = None

    model_keys_raw = run_plan.get("model_keys")
    if not isinstance(model_keys_raw, list) or not model_keys_raw:
        blockers.append("run plan model_keys are missing")
        model_keys: list[str] = []
    else:
        model_keys = [
            str(value)
            for value in model_keys_raw
            if isinstance(value, str) and value
        ]
        if len(model_keys) != len(model_keys_raw):
            blockers.append("run plan model_keys contain invalid values")
        if len(set(model_keys)) != len(model_keys):
            blockers.append("run plan model_keys contain duplicates")

    if deterministic_baseline_case_ids != sealed_case_ids:
        missing = sealed_case_ids - deterministic_baseline_case_ids
        extra = deterministic_baseline_case_ids - sealed_case_ids
        if missing:
            blockers.append(
                "deterministic baseline missing cases: "
                + ", ".join(sorted(missing))
            )
        if extra:
            blockers.append(
                "deterministic baseline contains unknown cases: "
                + ", ".join(sorted(extra))
            )

    expected_keys = {
        (case_id, model_key, strategy_id)
        for case_id in sealed_case_ids
        for model_key in model_keys
        for strategy_id in (_DIRECT, _MAPPING, _REPAIR)
    }

    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    execution_ids: dict[str, tuple[str, str, str]] = {}
    outcome_counts: Counter[str] = Counter()
    provider_calls = 0
    repair_count = 0
    source_hash_by_case: dict[str, str] = {}

    for record in llm_records:
        if not isinstance(record, dict):
            blockers.append("execution record is malformed")
            continue
        try:
            key = _record_key(record)
        except ValueError as exc:
            blockers.append(str(exc))
            continue

        if key in by_key:
            blockers.append(
                "duplicate execution record for " + "/".join(key)
            )
            continue
        by_key[key] = record

        execution_id = record.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id:
            blockers.append("/".join(key) + ": execution_id is missing")
        elif execution_id in execution_ids:
            blockers.append(
                f"duplicate execution_id: {execution_id}"
            )
        else:
            execution_ids[execution_id] = key

        if record.get("schema_version") != "0.3.0":
            blockers.append(
                "/".join(key) + ": execution record schema_version must be 0.3.0"
            )

        record_freeze_hash = record.get("model_prompt_freeze_sha256")
        if not _valid_sha256(record_freeze_hash):
            blockers.append(
                "/".join(key) + ": model_prompt_freeze_sha256 is missing or invalid"
            )
        elif (
            expected_model_freeze_hash is not None
            and record_freeze_hash.lower()
            != str(expected_model_freeze_hash).lower()
        ):
            blockers.append(
                "/".join(key)
                + ": model_prompt_freeze_sha256 does not match run plan"
            )

        source_hash = record.get("source_input_sha256")
        if not _valid_sha256(source_hash):
            blockers.append(
                "/".join(key) + ": source_input_sha256 is missing or invalid"
            )
        else:
            normalized_source_hash = str(source_hash).lower()
            existing_source_hash = source_hash_by_case.get(key[0])
            if existing_source_hash is None:
                source_hash_by_case[key[0]] = normalized_source_hash
            elif existing_source_hash != normalized_source_hash:
                blockers.append(
                    f"{key[0]}: source_input_sha256 differs across planned arms"
                )

        outcome = record.get("outcome_class")
        if isinstance(outcome, str):
            outcome_counts[outcome] += 1
        else:
            blockers.append("/".join(key) + ": outcome_class is missing")

        strategy_id = key[2]
        generation_source = record.get("generation_source")
        if strategy_id in {_DIRECT, _MAPPING}:
            if generation_source != "provider_call":
                blockers.append(
                    "/".join(key) + ": provider strategy has wrong generation_source"
                )
            if record.get("attempt_number") != 1:
                blockers.append(
                    "/".join(key) + ": provider strategy attempt_number must be 1"
                )
            if record.get("source_execution_id") is not None:
                blockers.append(
                    "/".join(key) + ": provider strategy must not reference source_execution_id"
                )
            prompt_hash = record.get("rendered_prompt_sha256")
            if not _valid_sha256(prompt_hash):
                blockers.append(
                    "/".join(key)
                    + ": provider strategy rendered_prompt_sha256 is missing or invalid"
                )
            mapping_context_hash = record.get("mapping_context_sha256")
            if strategy_id == _DIRECT:
                if mapping_context_hash is not None:
                    blockers.append(
                        "/".join(key)
                        + ": direct strategy must not record mapping_context_sha256"
                    )
            else:
                if not _valid_sha256(mapping_context_hash):
                    blockers.append(
                        "/".join(key)
                        + ": mapping strategy mapping_context_sha256 is missing or invalid"
                    )
            provider_calls += 1
        elif strategy_id == _REPAIR:
            if generation_source != "reuse_mapping_aware_raw_output":
                blockers.append(
                    "/".join(key) + ": repair strategy has wrong generation_source"
                )
            if record.get("attempt_number") is not None:
                blockers.append(
                    "/".join(key) + ": repair strategy attempt_number must be null"
                )
            if record.get("provider_request_id") is not None:
                blockers.append(
                    "/".join(key) + ": repair strategy must not have provider_request_id"
                )
            if record.get("rendered_prompt_sha256") is not None:
                blockers.append(
                    "/".join(key)
                    + ": repair strategy must not record rendered_prompt_sha256"
                )
            if not _valid_sha256(record.get("mapping_context_sha256")):
                blockers.append(
                    "/".join(key)
                    + ": repair strategy mapping_context_sha256 is missing or invalid"
                )
            repair_count += 1
        else:
            blockers.append("/".join(key) + ": unknown strategy_id")

    observed_keys = set(by_key)
    missing_keys = sorted(expected_keys - observed_keys)
    unexpected_keys = sorted(observed_keys - expected_keys)
    if missing_keys:
        blockers.append(
            "missing planned LLM arm records: "
            + ", ".join("/".join(key) for key in missing_keys)
        )
    if unexpected_keys:
        blockers.append(
            "unexpected LLM arm records: "
            + ", ".join("/".join(key) for key in unexpected_keys)
        )

    for case_id in sorted(sealed_case_ids):
        for model_key in model_keys:
            mapping_key = (case_id, model_key, _MAPPING)
            repair_key = (case_id, model_key, _REPAIR)
            mapping = by_key.get(mapping_key)
            repair = by_key.get(repair_key)
            if mapping is None or repair is None:
                continue

            mapping_context_hash = mapping.get("mapping_context_sha256")
            repair_context_hash = repair.get("mapping_context_sha256")
            if (
                _valid_sha256(mapping_context_hash)
                and _valid_sha256(repair_context_hash)
                and str(mapping_context_hash).lower()
                != str(repair_context_hash).lower()
            ):
                blockers.append(
                    f"{case_id}/{model_key}: repair mapping-context hash does not "
                    "match mapping arm"
                )

            mapping_execution_id = mapping.get("execution_id")
            if repair.get("source_execution_id") != mapping_execution_id:
                blockers.append(
                    f"{case_id}/{model_key}: repair source_execution_id does not "
                    "match mapping execution"
                )

            mapping_outcome = mapping.get("outcome_class")
            repair_outcome = repair.get("outcome_class")
            if mapping_outcome == _RESPONSE:
                if repair_outcome == _UPSTREAM:
                    blockers.append(
                        f"{case_id}/{model_key}: upstream repair failure is invalid "
                        "when mapping response exists"
                    )
                if repair_outcome == _RESPONSE:
                    mapping_hash = mapping.get("raw_response_sha256")
                    repair_hash = repair.get("raw_response_sha256")
                    if mapping_hash != repair_hash:
                        blockers.append(
                            f"{case_id}/{model_key}: repair raw hash does not match "
                            "mapping raw hash"
                        )
                elif repair_outcome != _POSTPROCESS:
                    blockers.append(
                        f"{case_id}/{model_key}: successful mapping must yield "
                        "repair response or postprocessing failure"
                    )
            else:
                if repair_outcome != _UPSTREAM:
                    blockers.append(
                        f"{case_id}/{model_key}: failed mapping must propagate as "
                        "MEASUREMENT_FAILURE_UPSTREAM on repair arm"
                    )

    expected_counts = run_plan.get("expected_execution_counts")
    if not isinstance(expected_counts, dict):
        blockers.append("run plan expected_execution_counts are missing")
        expected_counts = {}

    baseline_count = len(deterministic_baseline_case_ids)
    total_outputs = len(llm_records) + baseline_count
    actual_counts = {
        "provider_generation_calls": provider_calls,
        "derived_repair_outputs": repair_count,
        "deterministic_baseline_outputs": baseline_count,
        "total_arm_outputs": total_outputs,
    }
    for key, actual in actual_counts.items():
        if expected_counts.get(key) != actual:
            blockers.append(
                f"actual {key} does not match run plan: "
                f"{actual} != {expected_counts.get(key)!r}"
            )

    return ConfirmatoryExecutionAudit(
        complete=not blockers,
        blockers=tuple(sorted(set(blockers))),
        provider_call_count=provider_calls,
        derived_repair_count=repair_count,
        deterministic_baseline_count=baseline_count,
        total_arm_output_count=total_outputs,
        outcome_counts=dict(sorted(outcome_counts.items())),
    )
