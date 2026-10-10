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
_PROVIDER_FAILURES = frozenset(
    {
        "MEASUREMENT_FAILURE_TRANSPORT",
        "MEASUREMENT_FAILURE_RATE_LIMIT",
        "MEASUREMENT_FAILURE_PROVIDER_5XX",
        "MEASUREMENT_FAILURE_TIMEOUT",
        "MEASUREMENT_FAILURE_AUTH_OR_CONFIG",
    }
)
_REPAIR_FAILURES = frozenset(
    {
        "MEASUREMENT_FAILURE_POSTPROCESSING",
        "MEASUREMENT_FAILURE_UPSTREAM",
    }
)


@dataclass(frozen=True)
class ModelExecutionRecord:
    schema_version: str
    execution_id: str
    case_id: str
    model_key: str
    model_prompt_freeze_sha256: str
    source_input_sha256: str
    rendered_prompt_sha256: str | None
    mapping_context_sha256: str | None
    strategy_id: str
    generation_source: str
    attempt_number: int | None
    source_execution_id: str | None
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


def _require_sha256(value: str | None, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise ValueError(f"{label} must be a 64-character SHA-256 hex digest")
    return value.lower()


def build_success_record(
    *,
    execution_id: str,
    case_id: str,
    model_key: str,
    model_prompt_freeze_sha256: str,
    source_input_sha256: str,
    rendered_prompt_sha256: str | None,
    mapping_context_sha256: str | None,
    strategy_output: StrategyOutput,
    request_started_at: str,
    request_finished_at: str,
    provider_request_id: str | None = None,
    source_execution_id: str | None = None,
) -> ModelExecutionRecord:
    """Build one immutable successful execution/derived-output record."""

    freeze_hash = _require_sha256(
        model_prompt_freeze_sha256,
        label="model_prompt_freeze_sha256",
    )
    source_hash = _require_sha256(
        source_input_sha256,
        label="source_input_sha256",
    )
    repair = strategy_output.syntax_repair
    repair_applied = bool(repair is not None and repair.changed)
    operations = repair.operations if repair is not None else ()

    if strategy_output.strategy_id in {DIRECT_STRATEGY, MAPPING_STRATEGY}:
        if repair is not None or repair_applied or operations:
            raise ValueError("non-repair strategies cannot record syntax repair")
        if strategy_output.final_output != strategy_output.raw_output:
            raise ValueError("non-repair strategy final output must equal raw output")
        if source_execution_id is not None:
            raise ValueError(
                "provider-call strategies cannot reference source_execution_id"
            )
        generation_source = "provider_call"
        attempt_number: int | None = 1
        prompt_hash = _require_sha256(
            rendered_prompt_sha256,
            label="rendered_prompt_sha256",
        )
        if strategy_output.strategy_id == DIRECT_STRATEGY:
            if mapping_context_sha256 is not None:
                raise ValueError(
                    "direct strategy cannot record mapping_context_sha256"
                )
            mapping_hash: str | None = None
        else:
            mapping_hash = _require_sha256(
                mapping_context_sha256,
                label="mapping_context_sha256",
            )
    elif strategy_output.strategy_id == REPAIR_STRATEGY:
        if repair is None:
            raise ValueError("repair strategy must provide repair metadata")
        if repair.input_sha256 != _digest(strategy_output.raw_output):
            raise ValueError("repair input hash does not match raw output")
        if repair.output_sha256 != _digest(strategy_output.final_output):
            raise ValueError("repair output hash does not match final output")
        if not isinstance(source_execution_id, str) or not source_execution_id:
            raise ValueError(
                "repair strategy requires the mapping source_execution_id"
            )
        if provider_request_id is not None:
            raise ValueError(
                "repair strategy reuses mapping output and has no provider_request_id"
            )
        generation_source = "reuse_mapping_aware_raw_output"
        attempt_number = None
        if rendered_prompt_sha256 is not None:
            raise ValueError(
                "repair strategy must not record rendered_prompt_sha256 because "
                "it does not make a provider call"
            )
        prompt_hash = None
        mapping_hash = _require_sha256(
            mapping_context_sha256,
            label="mapping_context_sha256",
        )
    else:
        raise ValueError(f"unsupported strategy_id: {strategy_output.strategy_id}")

    return ModelExecutionRecord(
        schema_version="0.3.0",
        execution_id=execution_id,
        case_id=case_id,
        model_key=model_key,
        model_prompt_freeze_sha256=freeze_hash,
        source_input_sha256=source_hash,
        rendered_prompt_sha256=prompt_hash,
        mapping_context_sha256=mapping_hash,
        strategy_id=strategy_output.strategy_id,
        generation_source=generation_source,
        attempt_number=attempt_number,
        source_execution_id=source_execution_id,
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
    model_prompt_freeze_sha256: str,
    source_input_sha256: str,
    rendered_prompt_sha256: str | None,
    mapping_context_sha256: str | None,
    strategy_id: str,
    outcome_class: str,
    request_started_at: str,
    request_finished_at: str,
    error_summary: str,
    provider_request_id: str | None = None,
    source_execution_id: str | None = None,
) -> ModelExecutionRecord:
    """Record one failed provider call or deterministic repair operation."""

    freeze_hash = _require_sha256(
        model_prompt_freeze_sha256,
        label="model_prompt_freeze_sha256",
    )
    source_hash = _require_sha256(
        source_input_sha256,
        label="source_input_sha256",
    )
    if strategy_id not in {DIRECT_STRATEGY, MAPPING_STRATEGY, REPAIR_STRATEGY}:
        raise ValueError(f"unsupported strategy_id: {strategy_id}")
    if not isinstance(error_summary, str) or not error_summary.strip():
        raise ValueError("failure record requires a non-empty error_summary")

    if strategy_id in {DIRECT_STRATEGY, MAPPING_STRATEGY}:
        if outcome_class not in _PROVIDER_FAILURES:
            raise ValueError(
                f"unsupported provider failure outcome_class: {outcome_class}"
            )
        if source_execution_id is not None:
            raise ValueError(
                "provider-call failure cannot reference source_execution_id"
            )
        generation_source = "provider_call"
        attempt_number: int | None = 1
        prompt_hash = _require_sha256(
            rendered_prompt_sha256,
            label="rendered_prompt_sha256",
        )
        if strategy_id == DIRECT_STRATEGY:
            if mapping_context_sha256 is not None:
                raise ValueError(
                    "direct strategy cannot record mapping_context_sha256"
                )
            mapping_hash: str | None = None
        else:
            mapping_hash = _require_sha256(
                mapping_context_sha256,
                label="mapping_context_sha256",
            )
    else:
        if outcome_class not in _REPAIR_FAILURES:
            raise ValueError(
                "repair failure must use a frozen derived-arm measurement failure"
            )
        if not isinstance(source_execution_id, str) or not source_execution_id:
            raise ValueError(
                "repair failure requires the mapping source_execution_id"
            )
        if provider_request_id is not None:
            raise ValueError(
                "repair failure cannot have provider_request_id"
            )
        generation_source = "reuse_mapping_aware_raw_output"
        attempt_number = None
        if rendered_prompt_sha256 is not None:
            raise ValueError(
                "repair failure cannot record rendered_prompt_sha256"
            )
        prompt_hash = None
        mapping_hash = _require_sha256(
            mapping_context_sha256,
            label="mapping_context_sha256",
        )

    return ModelExecutionRecord(
        schema_version="0.2.0",
        execution_id=execution_id,
        case_id=case_id,
        model_key=model_key,
        model_prompt_freeze_sha256=freeze_hash,
        source_input_sha256=source_hash,
        rendered_prompt_sha256=prompt_hash,
        mapping_context_sha256=mapping_hash,
        strategy_id=strategy_id,
        generation_source=generation_source,
        attempt_number=attempt_number,
        source_execution_id=source_execution_id,
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
