from pathlib import Path

from fhirbridge.structural_validity_policy import (
    classify_fhir_operation_outcome,
    classify_fhir_validator_log,
    classify_nist_report,
)


def test_nist_errors_are_invalid_and_never_enter_vur_denominator() -> None:
    decision = classify_nist_report(
        {"error_total": 1, "warning_total": 0, "alert_total": 0}
    )

    assert decision.outcome == "INVALID"
    assert decision.enters_vur_denominator is False


def test_nist_warning_or_alert_is_policy_unresolved_prefreeze() -> None:
    warning = classify_nist_report(
        {"error_total": 0, "warning_total": 1, "alert_total": 0}
    )
    alert = classify_nist_report(
        {"error_total": 0, "warning_total": 0, "alert_total": 1}
    )

    assert warning.outcome == "POLICY_UNRESOLVED"
    assert alert.outcome == "POLICY_UNRESOLVED"
    assert not warning.enters_vur_denominator
    assert not alert.enters_vur_denominator


def test_clean_nist_report_is_valid() -> None:
    decision = classify_nist_report(
        {"error_total": 0, "warning_total": 0, "alert_total": 0}
    )

    assert decision.outcome == "VALID"
    assert decision.enters_vur_denominator


def test_nist_execution_or_report_failure_is_measurement_failure() -> None:
    assert classify_nist_report(
        None,
        validator_executed=False,
    ).outcome == "MEASUREMENT_FAILURE"
    assert classify_nist_report(None).outcome == "MEASUREMENT_FAILURE"
    assert classify_nist_report(
        {"error_total": 0, "warning_total": 0}
    ).outcome == "MEASUREMENT_FAILURE"


def test_fhir_error_is_invalid_warning_is_unresolved_information_is_valid() -> None:
    error = classify_fhir_operation_outcome(
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": "invalid"}],
        }
    )
    warning = classify_fhir_operation_outcome(
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "warning", "code": "business-rule"}],
        }
    )
    information = classify_fhir_operation_outcome(
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "information", "code": "informational"}],
        }
    )

    assert error.outcome == "INVALID"
    assert warning.outcome == "POLICY_UNRESOLVED"
    assert information.outcome == "VALID"


def test_unknown_fhir_severity_is_never_assumed_valid() -> None:
    decision = classify_fhir_operation_outcome(
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "mystery", "code": "unknown"}],
        }
    )

    assert decision.outcome == "POLICY_UNRESOLVED"
    assert not decision.enters_vur_denominator


_POLICY = Path("benchmark/fhir_validator_warning_policy.yaml")


def test_fhir_log_known_warning_is_valid_under_reviewed_policy(
    tmp_path: Path,
) -> None:
    log = tmp_path / "LAB-001.log"
    log.write_text(
        (
            "Warning @ Bundle.entry[0].resource: "
            "Constraint failed: dom-6: narrative\n"
            "Success: 0 errors, 1 warnings, 0 notes\n"
        ),
        encoding="utf-8",
    )

    decision = classify_fhir_validator_log(
        log,
        warning_policy_path=_POLICY,
    )

    assert decision.outcome == "VALID"
    assert decision.enters_vur_denominator
    assert any(
        "DOMAIN_RESOURCE_NARRATIVE_BEST_PRACTICE" in reason
        for reason in decision.reasons
    )


def test_fhir_log_unknown_warning_is_policy_unresolved(tmp_path: Path) -> None:
    log = tmp_path / "LAB-001.log"
    log.write_text(
        (
            "Warning @ Observation: unexpected new warning\n"
            "Success: 0 errors, 1 warnings, 0 notes\n"
        ),
        encoding="utf-8",
    )

    decision = classify_fhir_validator_log(
        log,
        warning_policy_path=_POLICY,
    )

    assert decision.outcome == "POLICY_UNRESOLVED"
    assert not decision.enters_vur_denominator


def test_fhir_log_error_is_invalid_even_with_known_warning(tmp_path: Path) -> None:
    log = tmp_path / "LAB-001.log"
    log.write_text(
        (
            "Warning @ Bundle.entry[0].resource: "
            "Constraint failed: dom-6: narrative\n"
            "Success: 1 errors, 1 warnings, 0 notes\n"
        ),
        encoding="utf-8",
    )

    decision = classify_fhir_validator_log(
        log,
        warning_policy_path=_POLICY,
    )

    assert decision.outcome == "INVALID"


def test_fhir_log_warning_count_mismatch_is_measurement_failure(
    tmp_path: Path,
) -> None:
    log = tmp_path / "LAB-001.log"
    log.write_text(
        (
            "Warning @ Bundle.entry[0].resource: "
            "Constraint failed: dom-6: narrative\n"
            "Success: 0 errors, 2 warnings, 0 notes\n"
        ),
        encoding="utf-8",
    )

    decision = classify_fhir_validator_log(
        log,
        warning_policy_path=_POLICY,
    )

    assert decision.outcome == "MEASUREMENT_FAILURE"


def test_fhir_log_missing_or_execution_failure_is_measurement_failure(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.log"

    assert classify_fhir_validator_log(
        missing,
        warning_policy_path=_POLICY,
    ).outcome == "MEASUREMENT_FAILURE"
    assert classify_fhir_validator_log(
        None,
        warning_policy_path=_POLICY,
        validator_executed=False,
    ).outcome == "MEASUREMENT_FAILURE"
