from copy import deepcopy

import yaml

from fhirbridge.measurement_policy_readiness import (
    assess_measurement_policies,
)

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.3.yaml"
_FAULTS = "fault_injection/fault_taxonomy_v0.1.yaml"
_SEVERITY = "benchmark/severity_policy_candidate.yaml"
_PRECEDENCE = "benchmark/error_precedence_policy_candidate.yaml"


def _yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _documents() -> tuple[dict, dict, dict, dict]:
    return (
        _yaml(_CONTRACT),
        _yaml(_FAULTS),
        _yaml(_SEVERITY),
        _yaml(_PRECEDENCE),
    )


def test_repository_measurement_policies_are_consistent_but_not_frozen() -> None:
    result = assess_measurement_policies(*_documents())

    assert result.consistent
    assert not result.freeze_ready
    assert result.consistency_blockers == ()
    assert any("severity policy status" in item for item in result.freeze_blockers)
    assert any("major threshold" in item for item in result.freeze_blockers)
    assert any("expert calibration" in item for item in result.freeze_blockers)
    assert any("precedence policy status" in item for item in result.freeze_blockers)


def test_precedence_drift_between_contract_and_policy_is_rejected() -> None:
    contract, faults, severity, precedence = _documents()
    mutated = deepcopy(contract)
    mutated["precedence"]["order"] = [
        "CORRUPTION",
        "MISATTRIBUTION",
        "OMISSION",
        "FABRICATION",
    ]

    result = assess_measurement_policies(
        mutated,
        faults,
        severity,
        precedence,
    )

    assert not result.consistent
    assert any("contract precedence differs" in item for item in result.consistency_blockers)


def test_fault_taxonomy_precedence_drift_is_rejected() -> None:
    contract, faults, severity, precedence = _documents()
    mutated = deepcopy(faults)
    mutated["precedence"] = [
        "MISATTRIBUTION",
        "OMISSION",
        "CORRUPTION",
        "FABRICATION",
    ]

    result = assess_measurement_policies(
        contract,
        mutated,
        severity,
        precedence,
    )

    assert not result.consistent
    assert any("fault taxonomy precedence differs" in item for item in result.consistency_blockers)


def test_undefined_contract_severity_default_is_rejected() -> None:
    contract, faults, severity, precedence = _documents()
    mutated = deepcopy(contract)
    mutated["rules"][0]["severity_default"] = "S9"

    result = assess_measurement_policies(
        mutated,
        faults,
        severity,
        precedence,
    )

    assert not result.consistent
    assert any("undefined severity_default" in item for item in result.consistency_blockers)


def test_expert_calibrated_frozen_policies_can_be_freeze_ready() -> None:
    contract, faults, severity, precedence = _documents()
    frozen_severity = deepcopy(severity)
    frozen_precedence = deepcopy(precedence)

    frozen_severity["severity_policy"]["status"] = "frozen"
    frozen_severity["primary_endpoint_major_candidate"]["status"] = "frozen"
    frozen_severity["primary_endpoint_major_candidate"]["threshold"] = (
        "S2_or_higher"
    )
    frozen_severity["expert_calibration"] = {
        "status": "completed",
        "record_ref": "expert_validation/severity-calibration.json",
        "record_sha256": "a" * 64,
    }
    frozen_precedence["precedence_policy"]["status"] = "frozen"
    frozen_precedence["expert_review"] = {
        "status": "completed",
        "review_ref": "expert_validation/precedence-review.yaml",
        "review_sha256": "b" * 64,
        "adjudicated_decision": "ACCEPT",
    }

    result = assess_measurement_policies(
        contract,
        faults,
        frozen_severity,
        frozen_precedence,
    )

    assert result.consistent
    assert result.freeze_ready
    assert result.consistency_blockers == ()
    assert result.freeze_blockers == ()


def test_expert_selected_s3_only_policy_can_be_freeze_ready() -> None:
    contract, faults, severity, precedence = _documents()
    frozen_severity = deepcopy(severity)
    frozen_precedence = deepcopy(precedence)

    frozen_severity["severity_policy"]["status"] = "frozen"
    frozen_severity["primary_endpoint_major_candidate"].update(
        {
            "status": "frozen",
            "threshold": "S3_only",
            "levels": ["S3"],
        }
    )
    frozen_severity["expert_calibration"] = {
        "status": "completed",
        "record_ref": "expert_validation/severity-calibration.json",
        "record_sha256": "a" * 64,
    }
    frozen_precedence["precedence_policy"]["status"] = "frozen"
    frozen_precedence["expert_review"] = {
        "status": "completed",
        "review_ref": "expert_validation/precedence-review.yaml",
        "review_sha256": "b" * 64,
        "adjudicated_decision": "ACCEPT",
    }

    result = assess_measurement_policies(
        contract,
        faults,
        frozen_severity,
        frozen_precedence,
    )

    assert result.consistent
    assert result.freeze_ready


def test_frozen_severity_threshold_must_match_included_levels() -> None:
    contract, faults, severity, precedence = _documents()
    frozen_severity = deepcopy(severity)
    frozen_precedence = deepcopy(precedence)

    frozen_severity["severity_policy"]["status"] = "frozen"
    frozen_severity["primary_endpoint_major_candidate"].update(
        {
            "status": "frozen",
            "threshold": "S3_only",
            "levels": ["S2", "S3"],
        }
    )
    frozen_severity["expert_calibration"] = {
        "status": "completed",
        "record_ref": "expert_validation/severity-calibration.json",
        "record_sha256": "a" * 64,
    }
    frozen_precedence["precedence_policy"]["status"] = "frozen"
    frozen_precedence["expert_review"] = {
        "status": "completed",
        "review_ref": "expert_validation/precedence-review.yaml",
        "review_sha256": "b" * 64,
        "adjudicated_decision": "ACCEPT",
    }

    result = assess_measurement_policies(
        contract,
        faults,
        frozen_severity,
        frozen_precedence,
    )

    assert not result.consistent
    assert any(
        "major levels do not match" in item
        for item in result.consistency_blockers
    )


def test_frozen_precedence_policy_requires_accepted_review_evidence() -> None:
    contract, faults, severity, precedence = _documents()
    frozen_severity = deepcopy(severity)
    frozen_precedence = deepcopy(precedence)

    frozen_severity["severity_policy"]["status"] = "frozen"
    frozen_severity["primary_endpoint_major_candidate"].update(
        {
            "status": "frozen",
            "threshold": "S2_or_higher",
        }
    )
    frozen_severity["expert_calibration"] = {
        "status": "completed",
        "record_ref": "expert_validation/severity-calibration.json",
        "record_sha256": "a" * 64,
    }
    frozen_precedence["precedence_policy"]["status"] = "frozen"

    result = assess_measurement_policies(
        contract,
        faults,
        frozen_severity,
        frozen_precedence,
    )

    assert not result.freeze_ready
    assert any(
        "precedence expert review evidence is missing" in item
        for item in result.freeze_blockers
    )
