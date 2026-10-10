import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from fhirbridge.sealed_case_manifest import (
    assess_sealed_case_manifest,
    sealed_case_ids,
    source_input_sha256_by_case,
)

_SCHEMA = Path("runs/schema/sealed_case_manifest.schema.json")
_TEMPLATE = Path("runs/examples/sealed_case_manifest_template.yaml")


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def _ready() -> dict:
    document = _template()
    document["manifest_id"] = "SEALED-CASES-001"
    document["status"] = "sealed"
    document["created_at"] = "2026-10-20T10:00:00Z"
    document["case_count"] = 2
    document["cases"] = [
        {
            "case_id": "CASE-001",
            "scenario_family": "LAB-001",
            "source_input_sha256": "1" * 64,
            "canonical_graph_sha256": "2" * 64,
        },
        {
            "case_id": "CASE-002",
            "scenario_family": "LAB-006",
            "source_input_sha256": "3" * 64,
            "canonical_graph_sha256": "4" * 64,
        },
    ]
    return document


def test_repository_template_is_schema_valid_but_not_ready() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_sealed_case_manifest(document)

    assert not readiness.ready
    assert any("status is not sealed" in item for item in readiness.blockers)
    assert any("placeholder" in item for item in readiness.blockers)


def test_ready_manifest_exposes_case_ids_and_source_hashes() -> None:
    document = _ready()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_sealed_case_manifest(document)

    assert readiness.ready
    assert sealed_case_ids(document) == {"CASE-001", "CASE-002"}
    assert source_input_sha256_by_case(document) == {
        "CASE-001": "1" * 64,
        "CASE-002": "3" * 64,
    }


def test_duplicate_case_id_is_rejected() -> None:
    document = _ready()
    document["cases"][1]["case_id"] = "CASE-001"

    readiness = assess_sealed_case_manifest(document)

    assert not readiness.ready
    assert any("duplicate sealed case_id" in item for item in readiness.blockers)


def test_case_count_must_match_case_array() -> None:
    document = _ready()
    document["case_count"] = 3

    readiness = assess_sealed_case_manifest(document)

    assert not readiness.ready
    assert any("case_count does not match" in item for item in readiness.blockers)


@pytest.mark.parametrize(
    "field",
    ["source_input_sha256", "canonical_graph_sha256"],
)
def test_case_hashes_fail_closed(field: str) -> None:
    document = _ready()
    document["cases"][0][field] = "0" * 64

    readiness = assess_sealed_case_manifest(document)

    assert not readiness.ready
    assert any(field in item for item in readiness.blockers)
