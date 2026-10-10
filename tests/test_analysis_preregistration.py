import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from fhirbridge.analysis_preregistration import (
    assess_analysis_preregistration,
)

_SCHEMA = Path("analysis/schema/analysis_preregistration.schema.json")
_TEMPLATE = Path("analysis/examples/analysis_preregistration_template.yaml")


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _ready() -> dict:
    document = _template()
    document["analysis_id"] = "ANALYSIS-001"
    document["status"] = "preregistered"
    document["created_at"] = "2026-10-20T12:00:00Z"
    document["frozen_inputs"].update(
        {
            "repository_commit": "abcdef1",
            "projectability_contract_sha256": "1" * 64,
            "structural_validity_policy_sha256": "2" * 64,
            "statistical_analysis_plan_sha256": "3" * 64,
        }
    )
    document["paired_comparisons"]["comparison_family"] = [
        {
            "comparison_id": "DIRECT_vs_MAPPING",
            "arm_a": "direct_structured_llm",
            "arm_b": "mapping_aware_llm",
        },
        {
            "comparison_id": "MAPPING_vs_REPAIR",
            "arm_a": "mapping_aware_llm",
            "arm_b": "mapping_aware_plus_syntax_repair",
        },
    ]
    document["bootstrap"]["seed"] = 20261020
    return document


def test_analysis_template_is_schema_valid_but_not_ready() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_analysis_preregistration(document)

    assert not readiness.ready
    assert any("not marked preregistered" in item for item in readiness.blockers)
    assert any("zero placeholder" in item for item in readiness.blockers)
    assert any("comparison_family" in item for item in readiness.blockers)
    assert any("bootstrap seed" in item for item in readiness.blockers)


def test_complete_analysis_preregistration_can_be_ready() -> None:
    document = _ready()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_analysis_preregistration(document)

    assert readiness.ready
    assert readiness.blockers == ()


def test_duplicate_unordered_comparison_pair_is_rejected() -> None:
    document = _ready()
    document["paired_comparisons"]["comparison_family"].append(
        {
            "comparison_id": "REVERSED_DUPLICATE",
            "arm_a": "mapping_aware_llm",
            "arm_b": "direct_structured_llm",
        }
    )

    readiness = assess_analysis_preregistration(document)

    assert not readiness.ready
    assert any("duplicate unordered comparison pair" in item for item in readiness.blockers)


def test_same_arm_comparison_is_rejected() -> None:
    document = _ready()
    document["paired_comparisons"]["comparison_family"][0]["arm_b"] = (
        "direct_structured_llm"
    )

    readiness = assess_analysis_preregistration(document)

    assert not readiness.ready
    assert any("arms must be distinct" in item for item in readiness.blockers)


def test_schema_forbids_opened_sealed_set() -> None:
    document = _ready()
    document["sealed_set_opened"] = True

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
