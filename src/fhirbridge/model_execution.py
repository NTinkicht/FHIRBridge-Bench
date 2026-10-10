"""Build immutable per-attempt records for confirmatory LLM execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

from .model_strategies import (
    DIRECT_STRATEGY,
    MAPPING_STRATEGY,
    REPAIR_STRATEGY,
    StrategyOutput,
)

_RESPONSE = "RESPONSE_RECEIVED"
_FAILURES = frozenset(
    {
        "MEASUREMENT_FAILURE_TRANSPORT",
        "MEASUREMENT_FAILURE_RATE_LIMIT",
        "MEASUREMENT_FAILURE_PROVIDER_5XX",
        "MEASUREMENT_FAILURE_TIMEOUT",
        "MEASUREMENT_FAILURE_AUTH_OR_CONFIG",
    }
)


@dataclass(frozen=True)
class ModelExecutionRecord:
    schema_version: str
    execution_id: str
    case_id: str
    model_key: str
    strategy_id: str
    attempt_number: int
    request_started_at: str
    request_finished_at: str
    outcome_class: str
    raw_response_sha256: str | None
    final_response_sha256: str | None
    syntax_repair_applied: bool
    syntax_repair_operations: tuple[str, ...]
    provider_request_id: str | None
    error_summary: str | None


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def build_success_record(
    *,
    execution_id: str,
    case_id: str,
    model_key: str,
    strategy_output: StrategyOutput,
    request_started_at: str,
    request_finished_at: str,
    provider_request_id: str | None = None,
) -> ModelExecutionRecord:
    """Build a successful-attempt record from actual strategy output."""

    repair = strategy_output.syntax_repair
    repair_applied = bool(repair is not None and repair.changed)
    operations = repair.operations if repair is not None else ()

    if strategy_output.strategy_id in {DIRECT_STRATEGY, MAPPING_STRATEGY}:
        if repair is not None or repair_applied or operations:
            raise ValueError("non-repair strategies cannot record syntax repair")
        if strategy_output.final_output != strategy_output.raw_output:
            raise ValueError("non-repair strategy final output must equal raw output")
    elif strategy_output.strategy_id == REPAIR_STRATEGY:
        if repair is None:
            raise ValueError("repair strategy must provide repair metadata")
        if repair.input_sha256 != _digest(strategy_output.raw_output):
            raise ValueError("repair input hash does not match raw output")
        if repair.output_sha256 != _digest(strategy_output.final_output):
            raise ValueError("repair output hash does not match final output")
    else:
        raise ValueError(f"unsupported strategy_id: {strategy_output.strategy_id}")

    return ModelExecutionRecord(
        schema_version="0.1.0",
        execution_id=execution_id,
        case_id=case_id,
        model_key=model_key,
        strategy_id=strategy_output.strategy_id,
        attempt_number=1,
        request_started_at=request_started_at,
        request_finished_at=request_finished_at,
        outcome_class=_RESPONSE,
        raw_response_sha256=_digest(strategy_output.raw_output),
        final_response_sha256=_digest(strategy_output.final_output),
        syntax_repair_applied=repair_applied,
        syntax_repair_operations=tuple(operations),
        provider_request_id=provider_request_id,
        error_summary=None,
    )


def build_failure_record(
    *,
    execution_id: str,
    case_id: str,
    model_key: str,
    strategy_id: str,
    outcome_class: str,
    request_started_at: str,
    request_finished_at: str,
    error_summary: str,
    provider_request_id: str | None = None,
) -> ModelExecutionRecord:
    """Record one failed provider attempt without fabricating response hashes."""

    if strategy_id not in {DIRECT_STRATEGY, MAPPING_STRATEGY, REPAIR_STRATEGY}:
        raise ValueError(f"unsupported strategy_id: {strategy_id}")
    if outcome_class not in _FAILURES:
        raise ValueError(f"unsupported failure outcome_class: {outcome_class}")
    if not isinstance(error_summary, str) or not error_summary.strip():
        raise ValueError("failure record requires a non-empty error_summary")

    return ModelExecutionRecord(
        schema_version="0.1.0",
        execution_id=execution_id,
        case_id=case_id,
        model_key=model_key,
        strategy_id=strategy_id,
        attempt_number=1,
        request_started_at=request_started_at,
        request_finished_at=request_finished_at,
        outcome_class=outcome_class,
        raw_response_sha256=None,
        final_response_sha256=None,
        syntax_repair_applied=False,
        syntax_repair_operations=(),
        provider_request_id=provider_request_id,
        error_summary=error_summary,
    )


def execution_record_to_dict(
    record: ModelExecutionRecord,
) -> dict[str, Any]:
    result = asdict(record)
    result["syntax_repair_operations"] = list(record.syntax_repair_operations)
    return result
