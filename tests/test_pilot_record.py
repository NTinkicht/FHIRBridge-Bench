import json
from pathlib import Path

import jsonschema
import pytest

from fhirbridge.pilot_acceptance import (
    assess_pilot_acceptance_preregistration,
)
from fhirbridge.pilot_record import build_pilot_acceptance_record

_SCHEMA = Path(
    "expert_validation/schema/pilot_acceptance_preregistration.schema.json"
)


def _schema() -> dict:
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _adjudications() -> list[dict]:
    return [
        {"case_id": "C1", "adjudicated_verdict": "YES"},
        {"case_id": "C2", "adjudicated_verdict": "YES"},
        {"case_id": "C3", "adjudicated_verdict": "NO"},
        {"case_id": "C4", "adjudicated_verdict": "NO"},
        {"case_id": "C5", "adjudicated_verdict": "INDETERMINATE"},
    ]


def _verifier() -> list[dict]:
    return [
        {"case_id": "C1", "semantic_verdict": "UNFAITHFUL"},
        {"case_id": "C2", "semantic_verdict": "INDETERMINATE"},
        {"case_id": "C3", "semantic_verdict": "FAITHFUL"},
        {"case_id": "C4", "semantic_verdict": "FAITHFUL"},
        {"case_id": "C5", "semantic_verdict": "UNFAITHFUL"},
    ]


def _build(**overrides) -> dict:
    args = {
        "adjudications": _adjudications(),
        "verifier_results": _verifier(),
        "record_id": "PILOT-001",
        "created_at": "2026-10-20T10:00:00Z",
        "pilot_case_manifest_sha256": "1" * 64,
        "repository_commit": "abcdef1",
        "verifier_sha256": "2" * 64,
        "projectability_contract_sha256": "3" * 64,
        "minimum_sensitivity": 0.4,
        "sensitivity_statistic": "point_estimate",
        "sensitivity_rationale": "Pilot-calibrated effective-sensitivity floor.",
        "minimum_ppv": 0.8,
        "ppv_statistic": "point_estimate",
        "ppv_rationale": "Pilot-calibrated determinate PPV floor.",
        "maximum_runtime_indeterminate_rate": 0.3,
        "indeterminate_statistic": "point_estimate",
        "indeterminate_rationale": "Pilot-calibrated abstention ceiling.",
    }
    args.update(overrides)
    return build_pilot_acceptance_record(**args)


def test_builder_preserves_expert_and_verifier_indeterminacy() -> None:
    record = _build()

    assert record["schema_version"] == "0.5.0"
    assert len(
        record["pilot_evidence"]["pilot_verifier_results_bundle_sha256"]
    ) == 64
    assert record["pilot_evidence"]["case_count"] == 5
    assert record["pilot_evidence"]["expert_major_error_positive_count"] == 2
    assert record["pilot_evidence"]["expert_major_error_negative_count"] == 2
    assert (
        record["pilot_evidence"]["expert_major_error_indeterminate_count"]
        == 1
    )
    assert record["metrics"]["runtime_indeterminate_count"] == 1
    assert (
        record["metrics"]["runtime_indeterminate_expert_positive_count"]
        == 1
    )
    assert (
        record["metrics"]["runtime_indeterminate_expert_negative_count"]
        == 0
    )
    assert record["metrics"]["true_positive"] == 1
    assert record["metrics"]["true_negative"] == 2
    assert record["metrics"]["false_positive"] == 0
    assert record["metrics"]["false_negative"] == 0
    assert record["metrics"]["sensitivity"]["estimate"] == pytest.approx(0.5)
    assert record["metrics"]["specificity"]["estimate"] == pytest.approx(1.0)
    assert record["metrics"]["accuracy"]["estimate"] == pytest.approx(0.75)
    assert record["metrics"]["runtime_indeterminate_rate"]["estimate"] == (
        pytest.approx(0.25)
    )


def test_generated_pilot_record_matches_schema_and_readiness_rules() -> None:
    record = _build()

    jsonschema.Draft202012Validator(_schema()).validate(record)
    readiness = assess_pilot_acceptance_preregistration(record)

    assert readiness.ready
    assert readiness.blockers == ()


def test_builder_requires_exact_case_set_match() -> None:
    verifier = _verifier()[:-1]

    with pytest.raises(ValueError, match="case sets must match exactly"):
        _build(verifier_results=verifier)


def test_expert_indeterminate_verifier_result_does_not_enter_binary_metrics() -> None:
    verifier = _verifier()
    verifier[-1] = {"case_id": "C5", "semantic_verdict": "INDETERMINATE"}

    record = _build(verifier_results=verifier)

    assert record["pilot_evidence"]["expert_major_error_indeterminate_count"] == 1
    assert record["metrics"]["runtime_indeterminate_count"] == 1


def test_builder_does_not_supply_default_acceptance_thresholds() -> None:
    with pytest.raises(TypeError):
        build_pilot_acceptance_record(
            adjudications=_adjudications(),
            verifier_results=_verifier(),
            record_id="PILOT-001",
            created_at="2026-10-20T10:00:00Z",
            pilot_case_manifest_sha256="1" * 64,
            repository_commit="abcdef1",
            verifier_sha256="2" * 64,
            projectability_contract_sha256="3" * 64,
        )


def test_verifier_bundle_hash_changes_when_verifier_results_change() -> None:
    first = _build()
    verifier = _verifier()
    verifier[3] = {"case_id": "C4", "semantic_verdict": "UNFAITHFUL"}
    second = _build(verifier_results=verifier)

    assert (
        first["pilot_evidence"]["pilot_verifier_results_bundle_sha256"]
        != second["pilot_evidence"]["pilot_verifier_results_bundle_sha256"]
    )
