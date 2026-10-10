import json
from pathlib import Path

import jsonschema
import pytest
import yaml

_SCHEMA = Path(
    "expert_validation/schema/pilot_acceptance_preregistration.schema.json"
)
_TEMPLATE = Path(
    "expert_validation/examples/pilot_acceptance_preregistration_template.yaml"
)


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def test_incomplete_pilot_acceptance_template_is_schema_valid_but_not_a_claim() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)

    assert document["status"] == "incomplete_template"
    assert document["created_at"] is None


def test_pilot_acceptance_schema_forbids_opened_sealed_set() -> None:
    document = _template()
    document["timing_attestation"]["sealed_set_opened"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)


def test_pilot_acceptance_schema_forbids_using_sealed_results_for_thresholds() -> None:
    document = _template()
    document["timing_attestation"]["sealed_results_used_to_choose_thresholds"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
