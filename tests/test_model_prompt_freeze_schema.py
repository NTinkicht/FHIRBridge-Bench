from copy import deepcopy
from pathlib import Path

import json
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

    assert document["schema_version"] == "0.2.0"
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
