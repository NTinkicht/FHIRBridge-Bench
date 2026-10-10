"""Fail-closed readiness checks for confirmatory model/prompt freeze."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_STRATEGIES = frozenset(
    {
        "direct_structured_llm",
        "mapping_aware_llm",
        "mapping_aware_plus_syntax_repair",
    }
)
_MAPPING_STRATEGIES = frozenset(
    {"mapping_aware_llm", "mapping_aware_plus_syntax_repair"}
)
_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class ModelPromptFreezeReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zero_hash(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value.lower()) <= {"0"}
    )


def _artifact_blockers(
    artifact: Any,
    *,
    label: str,
    blockers: list[str],
) -> None:
    if not isinstance(artifact, dict):
        blockers.append(f"{label}: artifact is missing")
        return
    ref = artifact.get("path_or_ref")
    digest = artifact.get("sha256")
    if not isinstance(ref, str) or not ref or _placeholder(ref):
        blockers.append(f"{label}: path_or_ref is missing or placeholder")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or _zero_hash(digest)
    ):
        blockers.append(f"{label}: SHA-256 is missing or placeholder")


def assess_model_prompt_freeze(
    document: dict[str, Any],
) -> ModelPromptFreezeReadiness:
    blockers: list[str] = []

    if document.get("status") != "frozen":
        blockers.append("model/prompt configuration is not frozen")
    if document.get("created_at") is None:
        blockers.append("model/prompt freeze has no creation timestamp")
    if document.get("sealed_set_opened") is not False:
        blockers.append("sealed set must remain unopened at model/prompt freeze")
    if _placeholder(document.get("config_id")):
        blockers.append("model/prompt freeze config_id is still a placeholder")

    global_policy = document.get("global_execution_policy")
    if not isinstance(global_policy, dict):
        blockers.append("global_execution_policy is missing")
        global_policy = {}
    if global_policy.get("synthetic_data_only_for_hosted_models") is not True:
        blockers.append(
            "hosted-model execution is not restricted to synthetic data"
        )
    if global_policy.get("silent_model_fallback") is not False:
        blockers.append("silent model fallback must be disabled")
    if global_policy.get("silent_prompt_fallback") is not False:
        blockers.append("silent prompt fallback must be disabled")
    if global_policy.get("policy_id") != "FHIRBRIDGE-MODEL-EXECUTION-001":
        blockers.append("global execution policy_id is not frozen")
    if global_policy.get("policy_version") != "0.1.0":
        blockers.append("global execution policy_version is not frozen")
    _artifact_blockers(
        global_policy.get("policy_artifact"),
        label="global_execution_policy.policy_artifact",
        blockers=blockers,
    )
    if global_policy.get("logical_generation_attempts_per_case_arm_model") != 1:
        blockers.append("logical generation attempts must equal one")
    retry = global_policy.get("retry_policy")
    if not isinstance(retry, dict):
        blockers.append("retry_policy is missing")
    else:
        maximum_attempts = retry.get("maximum_attempts")
        if maximum_attempts != 1:
            blockers.append("retry maximum_attempts must equal one")
        retry_on = retry.get("retry_on")
        if retry_on != []:
            blockers.append("retry_on must be empty for confirmatory execution")
    timeout = global_policy.get("timeout_seconds")
    if timeout != 120:
        blockers.append("timeout_seconds must equal the frozen value 120")

    baseline = document.get("deterministic_baseline")
    if not isinstance(baseline, dict):
        blockers.append("deterministic_baseline is missing")
    else:
        _artifact_blockers(
            baseline.get("implementation_artifact"),
            label="deterministic_baseline.implementation_artifact",
            blockers=blockers,
        )

    models = document.get("llm_models")
    if not isinstance(models, list) or not models:
        blockers.append("at least one frozen LLM model is required")
        models = []

    model_keys: set[str] = set()
    model_identity_tuples: set[tuple[str, str, str]] = set()
    for index, model in enumerate(models):
        label = f"llm_models[{index}]"
        if not isinstance(model, dict):
            blockers.append(f"{label}: model entry is malformed")
            continue

        model_key = model.get("model_key")
        if (
            not isinstance(model_key, str)
            or not model_key
            or _placeholder(model_key)
        ):
            blockers.append(f"{label}: model_key is missing or placeholder")
        elif model_key in model_keys:
            blockers.append(f"duplicate model_key: {model_key}")
        else:
            model_keys.add(model_key)

        identity: list[str] = []
        for field in ("provider", "model_id", "model_revision_or_snapshot"):
            value = model.get(field)
            if (
                not isinstance(value, str)
                or not value
                or _placeholder(value)
            ):
                blockers.append(f"{label}: {field} is missing or placeholder")
                identity.append("")
            else:
                identity.append(value)
        if all(identity):
            identity_tuple = tuple(identity)
            if identity_tuple in model_identity_tuples:
                blockers.append(
                    f"{label}: duplicate provider/model/snapshot identity"
                )
            model_identity_tuples.add(identity_tuple)

        temperature = model.get("temperature")
        top_p = model.get("top_p")
        max_tokens = model.get("max_output_tokens")
        if not isinstance(temperature, (int, float)) or temperature < 0:
            blockers.append(f"{label}: temperature must be >= 0")
        if not isinstance(top_p, (int, float)) or not 0 < top_p <= 1:
            blockers.append(f"{label}: top_p must be in (0,1]")
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or max_tokens < 1
        ):
            blockers.append(
                f"{label}: max_output_tokens must be a positive integer"
            )

        structured = model.get("structured_output_mode")
        if (
            not isinstance(structured, str)
            or not structured
            or _placeholder(structured)
        ):
            blockers.append(
                f"{label}: structured_output_mode is missing or placeholder"
            )

        seed_policy = model.get("seed_policy")
        seed = model.get("seed")
        if seed_policy == "fixed_supported_seed":
            if (
                not isinstance(seed, int)
                or isinstance(seed, bool)
                or seed < 0
            ):
                blockers.append(f"{label}: fixed seed is missing")
        elif seed_policy == "provider_does_not_support_seed":
            if seed is not None:
                blockers.append(
                    f"{label}: seed must be null when provider has no seed support"
                )
        else:
            blockers.append(f"{label}: seed_policy is invalid")

    strategies = document.get("llm_strategies")
    if not isinstance(strategies, list):
        blockers.append("llm_strategies must be a list")
        strategies = []

    by_id: dict[str, dict[str, Any]] = {}
    for strategy in strategies:
        if not isinstance(strategy, dict):
            blockers.append("LLM strategy entry is malformed")
            continue
        strategy_id = strategy.get("strategy_id")
        if not isinstance(strategy_id, str):
            blockers.append("strategy_id is missing")
            continue
        if strategy_id in by_id:
            blockers.append(f"duplicate strategy_id: {strategy_id}")
        by_id[strategy_id] = strategy

    if set(by_id) != _STRATEGIES:
        blockers.append(
            "model/prompt freeze must contain exactly the three LLM strategies"
        )

    for strategy_id, strategy in by_id.items():
        _artifact_blockers(
            strategy.get("implementation_artifact"),
            label=f"{strategy_id}.implementation_artifact",
            blockers=blockers,
        )
        prompts = strategy.get("prompt_artifacts")
        mappings = strategy.get("mapping_context_artifacts")
        repair = strategy.get("syntax_repair")

        if not isinstance(prompts, list) or not prompts:
            blockers.append(
                f"{strategy_id}: at least one frozen prompt artifact is required"
            )
            prompts = []
        for index, artifact in enumerate(prompts):
            _artifact_blockers(
                artifact,
                label=f"{strategy_id}.prompt_artifacts[{index}]",
                blockers=blockers,
            )

        if not isinstance(mappings, list):
            blockers.append(
                f"{strategy_id}: mapping_context_artifacts must be a list"
            )
            mappings = []
        if strategy_id in _MAPPING_STRATEGIES:
            if not mappings:
                blockers.append(
                    f"{strategy_id}: frozen mapping-context artifacts are required"
                )
        elif mappings:
            blockers.append(
                f"{strategy_id}: direct strategy must not receive mapping context"
            )
        for index, artifact in enumerate(mappings):
            _artifact_blockers(
                artifact,
                label=f"{strategy_id}.mapping_context_artifacts[{index}]",
                blockers=blockers,
            )

        if not isinstance(repair, dict):
            blockers.append(f"{strategy_id}: syntax_repair is missing")
            continue
        repair_expected = (
            strategy_id == "mapping_aware_plus_syntax_repair"
        )
        if repair.get("enabled") is not repair_expected:
            blockers.append(
                f"{strategy_id}: syntax-repair enabled flag does not match strategy"
            )
        repair_artifact = repair.get("implementation_artifact")
        if repair_expected:
            _artifact_blockers(
                repair_artifact,
                label=(
                    f"{strategy_id}.syntax_repair.implementation_artifact"
                ),
                blockers=blockers,
            )
        elif repair_artifact is not None:
            blockers.append(
                f"{strategy_id}: syntax repair artifact must be null when disabled"
            )

    return ModelPromptFreezeReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
