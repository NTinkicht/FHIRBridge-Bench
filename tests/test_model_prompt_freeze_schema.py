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

    assert document["status"] == "incomplete_template"
    assert document["sealed_set_opened"] is False
    assert {arm["arm_id"] for arm in document["arms"]} == {
        "deterministic_baseline",
        "direct_structured_llm",
        "mapping_aware_llm",
        "mapping_aware_plus_syntax_repair",
    }


def test_model_prompt_schema_forbids_opened_sealed_set() -> None:
    document = _template()
    document["sealed_set_opened"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_exactly_four_core_arms() -> None:
    document = _template()
    document["arms"].pop()

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_rejects_unknown_arm() -> None:
    document = deepcopy(_template())
    document["arms"][0]["arm_id"] = "unknown_arm"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_model_prompt_schema_requires_sha256_artifacts() -> None:
    document = _template()
    document["arms"][0]["implementation_artifact"]["sha256"] = "bad"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
