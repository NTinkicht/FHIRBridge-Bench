import yaml

from fhirbridge.pilot_acceptance import (
    assess_pilot_acceptance_preregistration,
)

_TEMPLATE = "expert_validation/examples/pilot_acceptance_preregistration_template.yaml"


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_incomplete_pilot_gate_template_is_not_freeze_ready() -> None:
    readiness = assess_pilot_acceptance_preregistration(_template())

    assert not readiness.ready
    assert any("not marked preregistered" in blocker for blocker in readiness.blockers)
    assert any("zero placeholder" in blocker for blocker in readiness.blockers)
    assert any("rationale" in blocker for blocker in readiness.blockers)


def test_complete_pilot_gate_record_can_be_ready() -> None:
    record = _template()
    record["status"] = "preregistered"
    record["created_at"] = "2026-10-20T10:00:00Z"
    record["pilot_evidence"].update(
        {
            "pilot_case_manifest_sha256": "1" * 64,
            "pilot_adjudication_bundle_sha256": "2" * 64,
            "case_count": 10,
            "expert_major_error_positive_count": 4,
            "expert_major_error_negative_count": 6,
        }
    )
    record["frozen_instrument"].update(
        {
            "repository_commit": "abcdef1",
            "verifier_sha256": "3" * 64,
            "projectability_contract_sha256": "4" * 64,
        }
    )
    record["metrics"].update(
        {
            "true_positive": 3,
            "true_negative": 5,
            "false_positive": 1,
            "false_negative": 1,
            "runtime_indeterminate_count": 0,
            "runtime_indeterminate_expert_positive_count": 0,
            "runtime_indeterminate_expert_negative_count": 0,
        }
    )
    for name, estimate, lower, upper in (
        ("sensitivity", 0.75, 0.30, 0.95),
        ("specificity", 5 / 6, 0.44, 0.97),
        ("ppv", 0.75, 0.30, 0.95),
        ("npv", 5 / 6, 0.44, 0.97),
        ("accuracy", 0.8, 0.49, 0.94),
        ("runtime_indeterminate_rate", 0.0, 0.0, 0.28),
    ):
        record["metrics"][name] = {
            "estimate": estimate,
            "lower": lower,
            "upper": upper,
            "method": "Wilson_95_percent",
        }
    record["acceptance_gate"].update(
        {
            "minimum_sensitivity": 0.7,
            "sensitivity_statistic": "point_estimate",
            "sensitivity_rationale": "Pilot-calibrated prespecified measurement-use floor.",
            "minimum_ppv": 0.7,
            "ppv_statistic": "point_estimate",
            "ppv_rationale": "Pilot-calibrated prespecified false-positive tolerance.",
            "maximum_runtime_indeterminate_rate": 0.2,
            "indeterminate_statistic": "point_estimate",
            "indeterminate_rationale": (
                "Pilot-calibrated prespecified unresolved-measurement ceiling."
            ),
        }
    )

    readiness = assess_pilot_acceptance_preregistration(record)

    assert readiness.ready
    assert readiness.blockers == ()


def test_confusion_counts_must_match_pilot_case_count() -> None:
    record = _template()
    record["pilot_evidence"]["case_count"] = 12

    readiness = assess_pilot_acceptance_preregistration(record)

    assert any(
        "confusion counts do not sum to determinate case count" in blocker
        for blocker in readiness.blockers
    )


def test_pilot_gate_checks_indeterminate_rate_count_consistency() -> None:
    record = _template()
    record["pilot_evidence"]["case_count"] = 10
    record["metrics"]["runtime_indeterminate_count"] = 2
    record["metrics"]["runtime_indeterminate_expert_positive_count"] = 1
    record["metrics"]["runtime_indeterminate_expert_negative_count"] = 1
    record["metrics"]["runtime_indeterminate_rate"]["estimate"] = 0.1

    readiness = assess_pilot_acceptance_preregistration(record)

    assert any(
        "runtime_indeterminate_rate estimate does not match" in blocker
        for blocker in readiness.blockers
    )


def test_pilot_confusion_counts_exclude_indeterminate_cases() -> None:
    record = _template()
    record["pilot_evidence"]["case_count"] = 10
    record["pilot_evidence"]["expert_major_error_positive_count"] = 4
    record["pilot_evidence"]["expert_major_error_negative_count"] = 6
    record["metrics"].update(
        {
            "true_positive": 3,
            "true_negative": 4,
            "false_positive": 1,
            "false_negative": 0,
            "runtime_indeterminate_count": 2,
            "runtime_indeterminate_expert_positive_count": 1,
            "runtime_indeterminate_expert_negative_count": 1,
        }
    )
    record["metrics"]["runtime_indeterminate_rate"]["estimate"] = 0.2

    readiness = assess_pilot_acceptance_preregistration(record)

    assert not any(
        "confusion counts do not sum to determinate case count" in blocker
        for blocker in readiness.blockers
    )


def test_pilot_gate_rejects_sensitivity_that_excludes_positive_abstentions() -> None:
    record = _template()
    record["status"] = "preregistered"
    record["created_at"] = "2026-10-20T10:00:00Z"
    record["pilot_evidence"].update(
        {
            "pilot_case_manifest_sha256": "1" * 64,
            "pilot_adjudication_bundle_sha256": "2" * 64,
            "case_count": 8,
            "expert_major_error_positive_count": 4,
            "expert_major_error_negative_count": 4,
        }
    )
    record["frozen_instrument"].update(
        {
            "repository_commit": "abcdef1",
            "verifier_sha256": "3" * 64,
            "projectability_contract_sha256": "4" * 64,
        }
    )
    record["metrics"].update(
        {
            "true_positive": 2,
            "true_negative": 4,
            "false_positive": 0,
            "false_negative": 0,
            "runtime_indeterminate_count": 2,
            "runtime_indeterminate_expert_positive_count": 2,
            "runtime_indeterminate_expert_negative_count": 0,
        }
    )
    record["metrics"]["sensitivity"]["estimate"] = 1.0
    record["metrics"]["specificity"]["estimate"] = 1.0
    record["metrics"]["ppv"]["estimate"] = 1.0
    record["metrics"]["npv"]["estimate"] = 1.0
    record["metrics"]["accuracy"]["estimate"] = 0.75
    record["metrics"]["runtime_indeterminate_rate"]["estimate"] = 0.25

    readiness = assess_pilot_acceptance_preregistration(record)

    assert any(
        "sensitivity estimate does not match frozen count semantics" in blocker
        for blocker in readiness.blockers
    )


def test_class_specific_abstentions_must_sum_to_total() -> None:
    record = _template()
    record["metrics"]["runtime_indeterminate_count"] = 2
    record["metrics"]["runtime_indeterminate_expert_positive_count"] = 2
    record["metrics"]["runtime_indeterminate_expert_negative_count"] = 1

    readiness = assess_pilot_acceptance_preregistration(record)

    assert any(
        "class-specific indeterminate counts do not sum" in blocker
        for blocker in readiness.blockers
    )


def test_expert_indeterminate_cases_are_retained_outside_metric_denominator() -> None:
    record = _template()
    record["pilot_evidence"].update(
        {
            "case_count": 12,
            "expert_major_error_positive_count": 4,
            "expert_major_error_negative_count": 6,
            "expert_major_error_indeterminate_count": 2,
        }
    )
    record["metrics"].update(
        {
            "true_positive": 3,
            "true_negative": 5,
            "false_positive": 1,
            "false_negative": 1,
            "runtime_indeterminate_count": 0,
            "runtime_indeterminate_expert_positive_count": 0,
            "runtime_indeterminate_expert_negative_count": 0,
        }
    )
    record["metrics"]["sensitivity"]["estimate"] = 0.75
    record["metrics"]["specificity"]["estimate"] = 5 / 6
    record["metrics"]["ppv"]["estimate"] = 0.75
    record["metrics"]["npv"]["estimate"] = 5 / 6
    record["metrics"]["accuracy"]["estimate"] = 0.8
    record["metrics"]["runtime_indeterminate_rate"]["estimate"] = 0.0

    readiness = assess_pilot_acceptance_preregistration(record)

    assert not any(
        "positive/negative/indeterminate counts do not sum" in blocker
        for blocker in readiness.blockers
    )
    assert not any(
        "confusion counts do not sum to determinate case count" in blocker
        for blocker in readiness.blockers
    )
    assert not any(
        "accuracy estimate does not match frozen count semantics" in blocker
        for blocker in readiness.blockers
    )
