from pathlib import Path

import pytest

from fhirbridge.model_strategies import (
    DIRECT_STRATEGY,
    MAPPING_STRATEGY,
    REPAIR_STRATEGY,
    prepare_strategy_prompt,
    process_strategy_output,
)


def _bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "p1",
                    "identifier": [{"value": "PAT-001"}],
                }
            }
        ],
    }


def test_repair_arm_cannot_prepare_a_second_provider_prompt() -> None:
    mapping = prepare_strategy_prompt(
        MAPPING_STRATEGY,
        _bundle(),
        mapping_context="RULE A -> FIELD X",
        repository_root=Path("."),
    )

    assert mapping.mapping_context_included
    with pytest.raises(ValueError, match="does not make a provider call"):
        prepare_strategy_prompt(
            REPAIR_STRATEGY,
            _bundle(),
            mapping_context="RULE A -> FIELD X",
            repository_root=Path("."),
        )


def test_direct_strategy_rejects_mapping_context() -> None:
    with pytest.raises(ValueError, match="must not receive mapping context"):
        prepare_strategy_prompt(
            DIRECT_STRATEGY,
            _bundle(),
            mapping_context="SHOULD NOT BE VISIBLE",
        )


def test_mapping_aware_strategy_requires_context() -> None:
    with pytest.raises(ValueError, match="require non-empty"):
        prepare_strategy_prompt(MAPPING_STRATEGY, _bundle())


def test_source_json_is_canonical_across_input_key_order() -> None:
    first = prepare_strategy_prompt(
        DIRECT_STRATEGY,
        {"b": 2, "a": 1},
    )
    second = prepare_strategy_prompt(
        DIRECT_STRATEGY,
        {"a": 1, "b": 2},
    )

    assert first.source_json == second.source_json == '{"a":1,"b":2}'
    assert first.rendered_prompt == second.rendered_prompt


def test_direct_and_mapping_arms_do_not_postprocess_model_output() -> None:
    fence = chr(96) * 3
    raw = fence + "hl7\nMSH|^~\\&|APP\n" + fence

    direct = process_strategy_output(DIRECT_STRATEGY, raw)
    mapping = process_strategy_output(MAPPING_STRATEGY, raw)

    assert direct.final_output == raw
    assert mapping.final_output == raw
    assert direct.syntax_repair is None
    assert mapping.syntax_repair is None


def test_repair_arm_applies_only_deterministic_syntax_repair() -> None:
    fence = chr(96) * 3
    raw = fence + "hl7\nMSH|^~\\&|APP\nPID|1||P1\n" + fence

    output = process_strategy_output(REPAIR_STRATEGY, raw)

    assert output.final_output == "MSH|^~\\&|APP\rPID|1||P1\r"
    assert output.syntax_repair is not None
    assert output.syntax_repair.changed


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported strategy_id"):
        prepare_strategy_prompt("other", _bundle())

    with pytest.raises(ValueError, match="unsupported strategy_id"):
        process_strategy_output("other", "MSH|")
