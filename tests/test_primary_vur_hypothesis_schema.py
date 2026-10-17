import json
from pathlib import Path

import jsonschema
import pytest
import yaml

_SCHEMA = Path(
    "analysis/schema/primary_vur_hypothesis_preregistration.schema.json"
)
_TEMPLATE = Path(
    "analysis/examples/primary_vur_hypothesis_preregistration_template.yaml"
)


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def test_primary_vur_hypothesis_template_is_schema_valid_nonassertive() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)

    assert document["status"] == "incomplete_template"
    assert document["sealed_set_opened"] is False


def test_primary_vur_hypothesis_schema_forbids_opened_sealed_set() -> None:
    document = _template()
    document["sealed_set_opened"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_primary_vur_hypothesis_schema_requires_nonzero_threshold() -> None:
    document = _template()
    document["hypothesis"]["nontrivial_vur_threshold"] = 0.0

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
