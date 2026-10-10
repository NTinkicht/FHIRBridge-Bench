"""Fail-closed structural-validity classification for endpoint denominators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_OUTCOMES = frozenset(
    {"VALID", "INVALID", "MEASUREMENT_FAILURE", "POLICY_UNRESOLVED"}
)


@dataclass(frozen=True)
class StructuralValidityDecision:
    outcome: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOMES:
            raise ValueError(f"unsupported structural-validity outcome: {self.outcome}")

    @property
    def enters_vur_denominator(self) -> bool:
        return self.outcome == "VALID"


def classify_nist_report(
    report: dict[str, Any] | None,
    *,
    validator_executed: bool = True,
    profile_loaded: bool = True,
) -> StructuralValidityDecision:
    """Classify one pinned NIST report without treating uncertainty as valid."""

    if not validator_executed:
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("validator_execution_failed",),
        )
    if not profile_loaded:
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("profile_load_failed",),
        )
    if not isinstance(report, dict):
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("validator_report_missing_or_malformed",),
        )

    required = ("error_total", "warning_total", "alert_total")
    if any(key not in report for key in required):
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("validator_classification_counts_missing",),
        )

    try:
        error_total = int(report["error_total"])
        warning_total = int(report["warning_total"])
        alert_total = int(report["alert_total"])
    except (TypeError, ValueError):
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("validator_classification_counts_not_numeric",),
        )

    if min(error_total, warning_total, alert_total) < 0:
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("validator_classification_counts_negative",),
        )

    if error_total:
        return StructuralValidityDecision(
            "INVALID",
            ("nist_error_classification_present",),
        )
    unresolved: list[str] = []
    if warning_total:
        unresolved.append("nist_warning_policy_not_frozen")
    if alert_total:
        unresolved.append("nist_alert_policy_not_frozen")
    if unresolved:
        return StructuralValidityDecision(
            "POLICY_UNRESOLVED",
            tuple(unresolved),
        )
    return StructuralValidityDecision("VALID", ())


def classify_fhir_operation_outcome(
    operation_outcome: dict[str, Any] | None,
    *,
    validator_executed: bool = True,
    package_loaded: bool = True,
) -> StructuralValidityDecision:
    """Classify FHIR validator severities using the pre-freeze candidate policy."""

    if not validator_executed:
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("validator_execution_failed",),
        )
    if not package_loaded:
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("fhir_package_load_failed",),
        )
    if not isinstance(operation_outcome, dict):
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("operation_outcome_missing_or_malformed",),
        )
    if operation_outcome.get("resourceType") != "OperationOutcome":
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("operation_outcome_resource_type_invalid",),
        )
    issues = operation_outcome.get("issue", [])
    if not isinstance(issues, list):
        return StructuralValidityDecision(
            "MEASUREMENT_FAILURE",
            ("operation_outcome_issue_not_list",),
        )

    severities: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            return StructuralValidityDecision(
                "MEASUREMENT_FAILURE",
                ("operation_outcome_issue_malformed",),
            )
        severity = issue.get("severity")
        if not isinstance(severity, str):
            return StructuralValidityDecision(
                "MEASUREMENT_FAILURE",
                ("operation_outcome_severity_missing",),
            )
        if severity not in {"fatal", "error", "warning", "information"}:
            return StructuralValidityDecision(
                "POLICY_UNRESOLVED",
                (f"unknown_fhir_severity:{severity}",),
            )
        severities.add(severity)

    if severities & {"fatal", "error"}:
        return StructuralValidityDecision(
            "INVALID",
            ("fhir_fatal_or_error_present",),
        )
    if "warning" in severities:
        return StructuralValidityDecision(
            "POLICY_UNRESOLVED",
            ("fhir_warning_policy_not_frozen",),
        )
    return StructuralValidityDecision("VALID", ())
