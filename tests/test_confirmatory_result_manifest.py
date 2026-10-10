import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from fhirbridge.confirmatory_result_manifest import (
    assess_confirmatory_result_manifest,
)

_SCHEMA = Path("runs/schema/confirmatory_result_manifest.schema.json")
_TEMPLATE = Path("runs/examples/confirmatory_result_manifest_template.yaml")


def _template() -> dict:
    return yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _run_plan() -> dict:
    return {
        "sealed_set": {
            "bundle_sha256": "a" * 64,
            "case_count": 10,
        },
        "model_keys": ["M1", "M2"],
        "expected_execution_counts": {
            "provider_generation_calls": 40,
            "derived_repair_outputs": 20,
            "deterministic_baseline_outputs": 10,
            "total_arm_outputs": 70,
        },
    }


def _ready() -> dict:
    document = _template()
    document.update(
        {
            "result_manifest_id": "RESULTS-001",
            "status": "execution_complete_audited",
            "created_at": "2026-10-21T10:00:00Z",
            "repository_commit": "abcdef1",
            "run_plan_sha256": "1" * 64,
            "sealed_bundle_sha256": "a" * 64,
        }
    )
    document["raw_execution_records"].update(
        {
            "path_or_ref": "runs/results/execution-records.jsonl",
            "sha256": "2" * 64,
            "record_count": 60,
        }
    )
    document["deterministic_baseline_outputs"].update(
        {
            "path_or_ref": "runs/results/baseline.jsonl",
            "sha256": "3" * 64,
            "record_count": 10,
        }
    )
    document["execution_audit"].update(
        {
            "path_or_ref": "runs/results/execution-audit.json",
            "sha256": "4" * 64,
            "complete": True,
        }
    )
    document["analysis_ready_dataset"].update(
        {
            "path_or_ref": "runs/results/analysis-rows.jsonl",
            "sha256": "5" * 64,
            "record_count": 20,
        }
    )
    return document


def test_repository_result_template_is_schema_valid_but_not_ready() -> None:
    document = _template()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_confirmatory_result_manifest(
        document,
        run_plan=_run_plan(),
        run_plan_sha256="1" * 64,
    )

    assert not readiness.ready
    assert any("not execution_complete_audited" in x for x in readiness.blockers)
    assert any("placeholder" in x for x in readiness.blockers)


def test_complete_result_manifest_matches_run_plan_counts() -> None:
    document = _ready()

    jsonschema.Draft202012Validator(_schema()).validate(document)
    readiness = assess_confirmatory_result_manifest(
        document,
        run_plan=_run_plan(),
        run_plan_sha256="1" * 64,
    )

    assert readiness.ready
    assert readiness.blockers == ()


@pytest.mark.parametrize(
    ("section", "wrong_count", "expected_fragment"),
    [
        ("raw_execution_records", 59, "3*N*M"),
        ("deterministic_baseline_outputs", 9, "does not equal N"),
        ("analysis_ready_dataset", 19, "does not equal N*M"),
    ],
)
def test_result_manifest_rejects_wrong_record_counts(
    section: str,
    wrong_count: int,
    expected_fragment: str,
) -> None:
    document = _ready()
    document[section]["record_count"] = wrong_count

    readiness = assess_confirmatory_result_manifest(
        document,
        run_plan=_run_plan(),
        run_plan_sha256="1" * 64,
    )

    assert not readiness.ready
    assert any(expected_fragment in x for x in readiness.blockers)


def test_result_manifest_must_bind_exact_run_plan_hash() -> None:
    document = _ready()

    readiness = assess_confirmatory_result_manifest(
        document,
        run_plan=_run_plan(),
        run_plan_sha256="f" * 64,
    )

    assert not readiness.ready
    assert any("run_plan_sha256" in x for x in readiness.blockers)


def test_result_manifest_must_bind_exact_sealed_bundle() -> None:
    document = _ready()
    document["sealed_bundle_sha256"] = "b" * 64

    readiness = assess_confirmatory_result_manifest(
        document,
        run_plan=_run_plan(),
        run_plan_sha256="1" * 64,
    )

    assert not readiness.ready
    assert any("sealed bundle hash" in x for x in readiness.blockers)


def test_execution_audit_must_be_complete() -> None:
    document = _ready()
    document["execution_audit"]["complete"] = False

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(document)
