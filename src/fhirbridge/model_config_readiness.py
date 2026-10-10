"""Fail-closed readiness checks for model/prompt confirmatory freeze."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_CORE_ARMS = frozenset(
    {
        "deterministic_baseline",
        "direct_structured_llm",
        "mapping_aware_llm",
        "mapping_aware_plus_syntax_repair",
    }
)
_LLM_ARMS = frozenset(_CORE_ARMS - {"deterministic_baseline"})
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
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= {"0"}


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
    if not isinstance(digest, str) or len(digest) != 64 or _zero_hash(digest):
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
        blockers.append("hosted-model execution is not restricted to synthetic data")
    if global_policy.get("silent_model_fallback") is not False:
        blockers.append("silent model fallback must be disabled")
    if global_policy.get("silent_prompt_fallback") is not False:
        blockers.append("silent prompt fallback must be disabled")
    retry = global_policy.get("retry_policy")
    if not isinstance(retry, dict):
        blockers.append("retry_policy is missing")
    else:
        maximum_attempts = retry.get("maximum_attempts")
        if not isinstance(maximum_attempts, int) or maximum_attempts < 1:
            blockers.append("retry maximum_attempts must be a positive integer")
    timeout = global_policy.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout < 1:
        blockers.append("timeout_seconds must be a positive integer")

    arms = document.get("arms")
    if not isinstance(arms, list):
        blockers.append("arms must be a list")
        arms = []

    by_id: dict[str, dict[str, Any]] = {}
    for arm in arms:
        if not isinstance(arm, dict):
            blockers.append("arm entry is malformed")
            continue
        arm_id = arm.get("arm_id")
        if not isinstance(arm_id, str):
            blockers.append("arm_id is missing")
            continue
        if arm_id in by_id:
            blockers.append(f"duplicate arm_id: {arm_id}")
        by_id[arm_id] = arm

    observed = set(by_id)
    if observed != _CORE_ARMS:
        blockers.append(
            "model/prompt freeze must contain exactly the four core arms"
        )

    for arm_id, arm in by_id.items():
        _artifact_blockers(
            arm.get("implementation_artifact"),
            label=f"{arm_id}.implementation_artifact",
            blockers=blockers,
        )
        prompt_artifacts = arm.get("prompt_artifacts")
        mapping_artifacts = arm.get("mapping_context_artifacts")
        syntax_repair = arm.get("syntax_repair")

        if not isinstance(prompt_artifacts, list):
            blockers.append(f"{arm_id}: prompt_artifacts must be a list")
            prompt_artifacts = []
        if not isinstance(mapping_artifacts, list):
            blockers.append(f"{arm_id}: mapping_context_artifacts must be a list")
            mapping_artifacts = []
        if not isinstance(syntax_repair, dict):
            blockers.append(f"{arm_id}: syntax_repair is missing")
            syntax_repair = {}

        if arm_id == "deterministic_baseline":
            if arm.get("implementation_kind") != "deterministic":
                blockers.append("deterministic_baseline must be deterministic")
            if arm.get("llm") is not None:
                blockers.append("deterministic_baseline must not define an LLM")
            if prompt_artifacts:
                blockers.append("deterministic_baseline must not have prompts")
            if mapping_artifacts:
                blockers.append(
                    "deterministic_baseline must not use LLM mapping-context artifacts"
                )
            if syntax_repair.get("enabled") is not False:
                blockers.append(
                    "deterministic_baseline syntax repair must be disabled"
                )
            continue

        if arm.get("implementation_kind") != "llm":
            blockers.append(f"{arm_id}: implementation_kind must be llm")
        llm = arm.get("llm")
        if not isinstance(llm, dict):
            blockers.append(f"{arm_id}: LLM configuration is missing")
            llm = {}
        for field in ("provider", "model_id", "model_revision_or_snapshot"):
            value = llm.get(field)
            if not isinstance(value, str) or not value or _placeholder(value):
                blockers.append(f"{arm_id}: {field} is missing or placeholder")
        structured = llm.get("structured_output_mode")
        if (
            not isinstance(structured, str)
            or not structured
            or _placeholder(structured)
        ):
            blockers.append(
                f"{arm_id}: structured_output_mode is missing or placeholder"
            )
        if llm.get("seed_policy") == "fixed_supported_seed":
            seed = llm.get("seed")
            if not isinstance(seed, int) or seed < 0:
                blockers.append(f"{arm_id}: fixed seed is missing")
        elif llm.get("seed_policy") == "provider_does_not_support_seed":
            if llm.get("seed") is not None:
                blockers.append(
                    f"{arm_id}: seed must be null when provider has no seed support"
                )
        else:
            blockers.append(f"{arm_id}: seed_policy is invalid")

        if not prompt_artifacts:
            blockers.append(f"{arm_id}: at least one frozen prompt artifact is required")
        for index, artifact in enumerate(prompt_artifacts):
            _artifact_blockers(
                artifact,
                label=f"{arm_id}.prompt_artifacts[{index}]",
                blockers=blockers,
            )

        if arm_id in {
            "mapping_aware_llm",
            "mapping_aware_plus_syntax_repair",
        }:
            if not mapping_artifacts:
                blockers.append(
                    f"{arm_id}: frozen mapping-context artifacts are required"
                )
        elif mapping_artifacts:
            blockers.append(
                f"{arm_id}: direct arm must not receive mapping-context artifacts"
            )
        for index, artifact in enumerate(mapping_artifacts):
            _artifact_blockers(
                artifact,
                label=f"{arm_id}.mapping_context_artifacts[{index}]",
                blockers=blockers,
            )

        repair_expected = arm_id == "mapping_aware_plus_syntax_repair"
        if syntax_repair.get("enabled") is not repair_expected:
            blockers.append(
                f"{arm_id}: syntax-repair enabled flag does not match arm definition"
            )
        repair_artifact = syntax_repair.get("implementation_artifact")
        if repair_expected:
            _artifact_blockers(
                repair_artifact,
                label=f"{arm_id}.syntax_repair.implementation_artifact",
                blockers=blockers,
            )
        elif repair_artifact is not None:
            blockers.append(
                f"{arm_id}: syntax repair artifact must be null when disabled"
            )

    llm_configs = [
        by_id[arm_id].get("llm")
        for arm_id in sorted(_LLM_ARMS)
        if isinstance(by_id.get(arm_id), dict)
    ]
    if len(llm_configs) == len(_LLM_ARMS) and all(
        isinstance(item, dict) for item in llm_configs
    ):
        fairness_fields = (
            "provider",
            "model_id",
            "model_revision_or_snapshot",
            "temperature",
            "top_p",
            "max_output_tokens",
            "seed_policy",
            "seed",
            "structured_output_mode",
        )
        baseline = llm_configs[0]
        for field in fairness_fields:
            values = {item.get(field) for item in llm_configs}
            if len(values) > 1:
                blockers.append(
                    f"LLM strategy arms differ on fairness-controlled field: {field}"
                )

    return ModelPromptFreezeReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
