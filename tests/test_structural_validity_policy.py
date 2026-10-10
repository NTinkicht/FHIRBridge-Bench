from fhirbridge.structural_validity_policy import (
    classify_fhir_operation_outcome,
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
