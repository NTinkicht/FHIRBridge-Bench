import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
import yaml

_SCHEMA = Path("models/schema/model_prompt_freeze.schema.json")
_TEMPLATE = Path("models/examples/model_prompt_freeze_template.yaml")


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def test_model_prompt_freeze_template_is_schema_valid_but_nonassertive() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)

    assert document["schema_version"] == "0.5.0"
    policy = document["global_execution_policy"]
    assert policy["policy_id"] == "FHIRBRIDGE-MODEL-EXECUTION-001"
    assert policy["policy_version"] == "0.3.0"
    assert policy["provider_generation_calls_per_case_model"] == {
        "direct_structured_llm": 1,
        "mapping_aware_llm": 1,
        "mapping_aware_plus_syntax_repair": 0,
    }
    assert policy["retry_policy"] == {"maximum_attempts": 1, "retry_on": []}
    assert policy["timeout_seconds"] == 120
    assert document["status"] == "incomplete_template"
    assert document["sealed_set_opened"] is False
    assert {
        strategy["strategy_id"]
        for strategy in document["llm_strategies"]
    } == {
        "direct_structured_llm",
        "mapping_aware_llm",
        "mapping_aware_plus_syntax_repair",
    }
    assert len(document["llm_models"]) >= 1
    assert all(
        model["structured_output_mode"] == "plain_text_hl7_message"
        for model in document["llm_models"]
    )


def test_model_prompt_schema_forbids_opened_sealed_set() -> None:
    document = _template()
    document["sealed_set_opened"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_exactly_three_llm_strategies() -> None:
    document = _template()
    document["llm_strategies"].pop()

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_rejects_unknown_strategy() -> None:
    document = deepcopy(_template())
    document["llm_strategies"][0]["strategy_id"] = "unknown_strategy"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_at_least_one_model() -> None:
    document = _template()
    document["llm_models"] = []

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_sha256_artifacts() -> None:
    document = _template()
    document["deterministic_baseline"]["implementation_artifact"][
        "sha256"
    ] = "bad"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_forbids_retry_drift() -> None:
    document = _template()
    document["global_execution_policy"]["retry_policy"]["maximum_attempts"] = 2

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_forbids_timeout_drift() -> None:
    document = _template()
    document["global_execution_policy"]["timeout_seconds"] = 121

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_forbids_extra_repair_provider_call() -> None:
    document = _template()
    document["global_execution_policy"][
        "provider_generation_calls_per_case_model"
    ]["mapping_aware_plus_syntax_repair"] = 1

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_repair_to_reuse_mapping_raw_output() -> None:
    document = _template()
    repair = next(
        strategy
        for strategy in document["llm_strategies"]
        if strategy["strategy_id"] == "mapping_aware_plus_syntax_repair"
    )
    repair["generation_source"] = "provider_call"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_rejects_non_hl7_output_mode() -> None:
    document = _template()
    document["llm_models"][0]["structured_output_mode"] = "json_schema"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_seed_when_supported() -> None:
    document = _template()
    model = document["llm_models"][0]
    model["seed_policy"] = "fixed_supported_seed"
    model["seed"] = None

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_null_seed_when_unsupported() -> None:
    document = _template()
    model = document["llm_models"][0]
    model["seed_policy"] = "provider_does_not_support_seed"
    model["seed"] = 123

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
