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


def _ready() -> dict:
    document = _template()
    document["config_id"] = "MODEL-FREEZE-001"
    document["status"] = "frozen"
    document["created_at"] = "2026-10-20T13:00:00Z"
    shared_llm = {
        "provider": "provider-x",
        "model_id": "model-y",
        "model_revision_or_snapshot": "snapshot-z",
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 4096,
        "seed_policy": "fixed_supported_seed",
        "seed": 20261020,
        "structured_output_mode": "json_schema",
    }
    for index, arm in enumerate(document["arms"], start=1):
        arm["implementation_artifact"] = _artifact(str(index))
        if arm["arm_id"] == "deterministic_baseline":
            continue
        arm["llm"] = dict(shared_llm)
        arm["prompt_artifacts"] = [_artifact(str(index + 3))]
        if arm["arm_id"] in {
            "mapping_aware_llm",
            "mapping_aware_plus_syntax_repair",
        }:
            arm["mapping_context_artifacts"] = [_artifact("8")]
        if arm["arm_id"] == "mapping_aware_plus_syntax_repair":
            arm["syntax_repair"]["implementation_artifact"] = _artifact("9")
    return document


def test_repository_model_prompt_template_is_deliberately_not_ready() -> None:
    readiness = assess_model_prompt_freeze(_template())

    assert not readiness.ready
    assert any("not frozen" in blocker for blocker in readiness.blockers)
    assert any("placeholder" in blocker for blocker in readiness.blockers)


def test_complete_fair_model_prompt_freeze_can_be_ready() -> None:
    readiness = assess_model_prompt_freeze(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_llm_strategy_arms_must_use_same_model_and_decoding() -> None:
    document = _ready()
    mapping = next(
        arm for arm in document["arms"]
        if arm["arm_id"] == "mapping_aware_llm"
    )
    mapping["llm"]["model_id"] = "different-model"

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "fairness-controlled field: model_id" in blocker
        for blocker in readiness.blockers
    )


def test_direct_arm_must_not_receive_mapping_context() -> None:
    document = _ready()
    direct = next(
        arm for arm in document["arms"]
        if arm["arm_id"] == "direct_structured_llm"
    )
    direct["mapping_context_artifacts"] = [_artifact("a")]

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any("direct arm must not receive" in blocker for blocker in readiness.blockers)


def test_repair_is_exclusive_to_repair_arm() -> None:
    document = _ready()
    mapping = next(
        arm for arm in document["arms"]
        if arm["arm_id"] == "mapping_aware_llm"
    )
    mapping["syntax_repair"]["enabled"] = True
    mapping["syntax_repair"]["implementation_artifact"] = _artifact("b")

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any(
        "syntax-repair enabled flag" in blocker
        for blocker in readiness.blockers
    )


def test_silent_model_fallback_is_prohibited() -> None:
    document = _ready()
    document["global_execution_policy"]["silent_model_fallback"] = True

    readiness = assess_model_prompt_freeze(document)

    assert not readiness.ready
    assert any("silent model fallback" in blocker for blocker in readiness.blockers)
