import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from fhirbridge.confirmatory_run_plan import assess_confirmatory_run_plan

_SCHEMA = Path("runs/schema/confirmatory_run_plan.schema.json")
_TEMPLATE = Path("runs/examples/confirmatory_run_plan_template.yaml")


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _ready() -> dict:
    document = _template()
    document["run_plan_id"] = "RUN-PLAN-001"
    document["status"] = "prepared_authorized"
    document["created_at"] = "2026-10-20T13:00:00Z"
    document["repository_commit"] = "abcdef1"
    document["authorization"]["record_sha256"] = "1" * 64
    document["authorization"]["record_schema_sha256"] = "f" * 64
    for index, key in enumerate(document["frozen_artifacts"], start=2):
        document["frozen_artifacts"][key] = f"{index:x}" * 64
    document["sealed_set"].update(
        {
            "bundle_id": "SEALED-001",
            "bundle_sha256": "a" * 64,
            "case_manifest_sha256": "b" * 64,
            "case_count": 10,
        }
    )
    document["model_keys"] = ["MODEL-A", "MODEL-B"]
    document["expected_execution_counts"] = {
        "provider_generation_calls": 40,
        "derived_repair_outputs": 20,
        "deterministic_baseline_outputs": 10,
        "total_arm_outputs": 70,
    }
    return document


def test_repository_run_plan_template_is_schema_valid_but_not_ready() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_confirmatory_run_plan(document)

    assert document["schema_version"] == "0.2.0"
    assert not readiness.ready
    assert any("not prepared_authorized" in item for item in readiness.blockers)
    assert any("placeholder" in item for item in readiness.blockers)


def test_ready_run_plan_recomputes_expected_execution_counts() -> None:
    document = _ready()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_confirmatory_run_plan(document)

    assert readiness.ready
    assert readiness.blockers == ()


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("provider_generation_calls", 39),
        ("derived_repair_outputs", 21),
        ("deterministic_baseline_outputs", 9),
        ("total_arm_outputs", 71),
    ],
)
def test_run_plan_rejects_wrong_expected_counts(
    field: str,
    wrong_value: int,
) -> None:
    document = _ready()
    document["expected_execution_counts"][field] = wrong_value

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any(field in item for item in readiness.blockers)


def test_run_plan_rejects_duplicate_model_keys() -> None:
    document = _ready()
    document["model_keys"] = ["MODEL-A", "MODEL-A"]

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any("duplicate model_key" in item for item in readiness.blockers)


def test_schema_forbids_opened_sealed_set_or_started_inference() -> None:
    for field in ("sealed_set_opened", "inference_started"):
        document = _ready()
        document[field] = True

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(_schema()).validate(document)


def test_run_plan_rejects_older_execution_record_contract() -> None:
    document = _ready()
    document["execution_record_contract"]["schema_version"] = "0.2.0"

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any(
        "schema_version is not frozen to 0.3.0" in item
        for item in readiness.blockers
    )


def test_run_plan_rejects_missing_execution_binding() -> None:
    document = _ready()
    document["execution_record_contract"]["required_bindings"].remove(
        "mapping_context_sha256"
    )

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any(
        "required_bindings do not match" in item
        for item in readiness.blockers
    )


def test_run_plan_requires_execution_schema_validation() -> None:
    document = _ready()
    document["execution_record_contract"]["schema_validation_required"] = False

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any(
        "schema validation is not required" in item
        for item in readiness.blockers
    )


def test_run_plan_rejects_wrong_authorization_schema_version() -> None:
    document = _ready()
    document["authorization"]["record_schema_version"] = "0.2.0"

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any(
        "authorization record schema_version" in item
        for item in readiness.blockers
    )


def test_run_plan_rejects_unfrozen_authorization_schema_hash() -> None:
    document = _ready()
    document["authorization"]["record_schema_sha256"] = "0" * 64

    readiness = assess_confirmatory_run_plan(document)

    assert not readiness.ready
    assert any(
        "authorization record schema SHA-256" in item
        for item in readiness.blockers
    )
