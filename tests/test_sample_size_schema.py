import json
from pathlib import Path

import jsonschema
import pytest
import yaml

_SCHEMA = Path("analysis/schema/sample_size_preregistration.schema.json")
_TEMPLATE = Path(
    "analysis/examples/sample_size_preregistration_template.yaml"
)


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def test_sample_size_template_is_schema_valid_and_nonassertive() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)

    assert document["schema_version"] == "0.3.0"
    assert document["status"] == "incomplete_template"
    assert document["sealed_set_opened"] is False


def test_sample_size_schema_forbids_opened_sealed_set() -> None:
    document = _template()
    document["sealed_set_opened"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_sample_size_schema_requires_six_paired_plans() -> None:
    document = _template()
    document["paired_comparison_plans"].pop()

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_sample_size_schema_requires_selection_rule() -> None:
    document = _template()
    del document["selection_rule"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_sample_size_schema_requires_source_cluster_attestation() -> None:
    document = _template()
    del document["attestation"][
        "final_source_cluster_count_recorded_before_confirmatory_inference"
    ]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
