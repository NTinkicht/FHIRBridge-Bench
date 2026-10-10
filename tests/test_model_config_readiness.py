import yaml

from fhirbridge.model_config_readiness import assess_model_prompt_freeze

_TEMPLATE = "models/examples/model_prompt_freeze_template.yaml"


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _artifact(seed: str) -> dict:
    return {
        "path_or_ref": f"frozen/{seed}.txt",
        "sha256": seed[0] * 64,
    }


def _model(
    key: str,
    *,
    provider: str = "provider-x",
    model_id: str | None = None,
) -> dict:
    return {
        "model_key": key,
        "provider": provider,
        "model_id": model_id or f"model-{key}",
        "model_revision_or_snapshot": f"snapshot-{key}",
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 4096,
        "seed_policy": "fixed_supported_seed",
        "seed": 20261020,
        "structured_output_mode": "plain_text_hl7_message",
    }


def _ready() -> dict:
    document = _template()
    document["config_id"] = "MODEL-FREEZE-001"
    document["status"] = "frozen"
    document["created_at"] = "2026-10-20T13:00:00Z"
    document["global_execution_policy"]["policy_artifact"] = {
        "path_or_ref": "models/execution_policy.yaml",
        "sha256": "e" * 64,
    }
    document["deterministic_baseline"]["implementation_artifact"] = _artifact(
        "1"
    )
    document["llm_models"] = [_model("M1"), _model("M2")]
    for index, strategy in enumerate(document["llm_strategies"], start=2):
        strategy["implementation_artifact"] = _artifact(str(index))
        if strategy["strategy_id"] == "direct_structured_llm":
            strategy["prompt_artifacts"] = [_artifact("5")]
        else:
            strategy["prompt_artifacts"] = [_artifact("6")]
            strategy["mapping_context_artifacts"] = [_artifact("8")]
        if (
            strategy["strategy_id"]
            == "mapping_aware_plus_syntax_repair"
        ):
            strategy["syntax_repair"]["implementation_artifact"] = _artifact(
                "9"
            )
    return document


def test_repository_model_prompt_template_is_deliberately_not_ready() -> None:
    readiness = assess_model_prompt_freeze(_template())

    assert not readiness.ready
    assert any("not frozen" in blocker for blocker in readiness.blockers)
    assert any("placeholder" in blocker for blocker in readiness.blockers)


def test_complete_crossed_multi_model_freeze_can_be_ready() -> None:
    readiness = assess_model_prompt_freeze(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_multiple_distinct_model_families_are_supported() -> None:
    document = _ready()
    document["llm_models"].append(
        _model("M3", provider="provider-y", model_id="another-family")
    )

    readiness = assess_model_prompt_freeze(document)

    assert readiness.ready


def test_duplicate_model_key_is_rejected() -> None:
    document = _ready()
    document["llm_models"].append(_model("M1", model_id="other"))

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any("duplicate model_key" in blocker for blocker in readiness.blockers)


def test_duplicate_provider_model_snapshot_identity_is_rejected() -> None:
    document = _ready()
    duplicate = dict(document["llm_models"][0])
    duplicate["model_key"] = "M3"
    document["llm_models"].append(duplicate)

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "duplicate provider/model/snapshot identity" in blocker
        for blocker in readiness.blockers
    )


def test_direct_strategy_must_not_receive_mapping_context() -> None:
    document = _ready()
    direct = next(
        strategy
        for strategy in document["llm_strategies"]
        if strategy["strategy_id"] == "direct_structured_llm"
    )
    direct["mapping_context_artifacts"] = [_artifact("a")]

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "direct strategy must not receive" in blocker
        for blocker in readiness.blockers
    )


def test_repair_is_exclusive_to_repair_strategy() -> None:
    document = _ready()
    mapping = next(
        strategy
        for strategy in document["llm_strategies"]
        if strategy["strategy_id"] == "mapping_aware_llm"
    )
    mapping["syntax_repair"]["enabled"] = True
    mapping["syntax_repair"]["implementation_artifact"] = _artifact("b")

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "syntax-repair enabled flag" in blocker
        for blocker in readiness.blockers
    )


def test_model_seed_policy_is_explicit() -> None:
    document = _ready()
    document["llm_models"][0]["seed_policy"] = (
        "provider_does_not_support_seed"
    )
    document["llm_models"][0]["seed"] = 20261020

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "seed must be null" in blocker for blocker in readiness.blockers
    )


def test_silent_model_fallback_is_prohibited() -> None:
    document = _ready()
    document["global_execution_policy"]["silent_model_fallback"] = True

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "silent model fallback" in blocker for blocker in readiness.blockers
    )


def test_retry_policy_must_match_frozen_one_attempt_policy() -> None:
    document = _ready()
    document["global_execution_policy"]["retry_policy"]["maximum_attempts"] = 2
    document["global_execution_policy"]["retry_policy"]["retry_on"] = [
        "transport_error"
    ]

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any("maximum_attempts must equal one" in blocker for blocker in readiness.blockers)
    assert any("retry_on must be empty" in blocker for blocker in readiness.blockers)


def test_timeout_must_match_frozen_120_seconds() -> None:
    document = _ready()
    document["global_execution_policy"]["timeout_seconds"] = 60

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any("timeout_seconds must equal" in blocker for blocker in readiness.blockers)


def test_execution_policy_artifact_must_be_hash_pinned() -> None:
    document = _ready()
    document["global_execution_policy"]["policy_artifact"]["sha256"] = "0" * 64

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "global_execution_policy.policy_artifact" in blocker
        for blocker in readiness.blockers
    )


def test_mapping_and_repair_prompts_must_be_identical() -> None:
    document = _ready()
    repair = next(
        strategy
        for strategy in document["llm_strategies"]
        if strategy["strategy_id"] == "mapping_aware_plus_syntax_repair"
    )
    repair["prompt_artifacts"] = [_artifact("a")]

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "must use identical prompt artifacts" in blocker
        for blocker in readiness.blockers
    )


def test_mapping_and_repair_context_must_be_identical() -> None:
    document = _ready()
    repair = next(
        strategy
        for strategy in document["llm_strategies"]
        if strategy["strategy_id"] == "mapping_aware_plus_syntax_repair"
    )
    repair["mapping_context_artifacts"] = [_artifact("b")]

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "must use identical mapping context artifacts" in blocker
        for blocker in readiness.blockers
    )


def test_repair_provider_generation_call_must_remain_zero() -> None:
    document = _ready()
    document["global_execution_policy"][
        "provider_generation_calls_per_case_model"
    ]["mapping_aware_plus_syntax_repair"] = 1

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "provider generation-call policy" in blocker
        for blocker in readiness.blockers
    )


def test_repair_generation_source_must_reuse_mapping_output() -> None:
    document = _ready()
    repair = next(
        strategy
        for strategy in document["llm_strategies"]
        if strategy["strategy_id"] == "mapping_aware_plus_syntax_repair"
    )
    repair["generation_source"] = "provider_call"

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "generation_source does not match frozen design" in blocker
        for blocker in readiness.blockers
    )


def test_structured_output_mode_is_frozen_to_plain_text_hl7() -> None:
    document = _ready()
    document["llm_models"][0]["structured_output_mode"] = "json_schema"

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "structured_output_mode must equal plain_text_hl7_message" in blocker
        for blocker in readiness.blockers
    )


def test_fixed_supported_seed_requires_concrete_nonnegative_integer() -> None:
    document = _ready()
    document["llm_models"][0]["seed_policy"] = "fixed_supported_seed"
    document["llm_models"][0]["seed"] = None

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any("fixed seed is missing" in blocker for blocker in readiness.blockers)
