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
