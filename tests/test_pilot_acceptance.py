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
        }
    )
    for name, estimate, lower, upper in (
        ("sensitivity", 0.75, 0.30, 0.95),
        ("specificity", 5 / 6, 0.44, 0.97),
        ("ppv", 0.75, 0.30, 0.95),
        ("npv", 5 / 6, 0.44, 0.97),
        ("accuracy", 0.8, 0.49, 0.94),
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
        "confusion counts do not sum to case_count" in blocker
        for blocker in readiness.blockers
    )
