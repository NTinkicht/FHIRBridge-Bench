from copy import deepcopy

import yaml

from fhirbridge.severity_calibration import (
    assess_severity_calibration,
)

_TEMPLATE = "expert_validation/examples/severity_calibration_template.yaml"


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _reviewer(reviewer_id: str) -> dict:
    return {
        "reviewer_id": reviewer_id,
        "expertise": ["laboratory clinical informatics"],
        "conflicts_of_interest": "None declared",
        "prior_project_involvement": "None",
    }


def _anchor(
    anchor_id: str,
    role: str,
    left: str,
    right: str,
    adjudicated: str,
) -> dict:
    return {
        "anchor_id": anchor_id,
        "anchor_description": f"Synthetic calibration anchor {anchor_id}",
        "expected_boundary_role": role,
        "reviewer_ratings": [
            {
                "reviewer_id": "R-A",
                "severity": left,
                "rationale": "Independent initial judgment A.",
            },
            {
                "reviewer_id": "R-B",
                "severity": right,
                "rationale": "Independent initial judgment B.",
            },
        ],
        "adjudicated_severity": adjudicated,
        "adjudication_rationale": "Consensus after preserving initial ratings.",
    }


def _ready() -> dict:
    document = _template()
    document["calibration_id"] = "SEVERITY-CAL-001"
    document["status"] = "completed"
    document["created_at"] = "2026-10-20T18:00:00Z"
    document["candidate_policy_sha256"] = "a" * 64
    document["reviewers"] = [_reviewer("R-A"), _reviewer("R-B")]
    document["anchor_reviews"] = [
        _anchor("A1", "S1_S2_boundary", "S1", "S2", "S2"),
        _anchor("A2", "S2_S3_boundary", "S2", "S3", "S3"),
        _anchor("A3", "clear_S2_anchor", "S2", "S2", "S2"),
        _anchor("A4", "clear_S3_anchor", "S3", "S3", "S3"),
    ]
    document["pre_adjudication_agreement"] = {
        "anchor_count": 4,
        "exact_agreement_count": 2,
        "exact_agreement_rate": 0.5,
        "disagreement_anchor_ids": ["A1", "A2"],
    }
    document["major_threshold_decision"] = {
        "threshold": "S2_or_higher",
        "included_levels": ["S2", "S3"],
        "rationale": (
            "S2 is clinically meaningful and S3 is potentially "
            "safety-critical."
        ),
        "decision_status": "frozen_for_confirmatory_endpoint",
    }
    return document


def test_repository_severity_calibration_template_is_not_ready() -> None:
    readiness = assess_severity_calibration(_template())

    assert not readiness.ready
    assert any("not marked completed" in item for item in readiness.blockers)
    assert any("placeholder" in item for item in readiness.blockers)
    assert any("SHA-256" in item for item in readiness.blockers)


def test_completed_severity_calibration_can_be_ready() -> None:
    readiness = assess_severity_calibration(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_pre_adjudication_agreement_is_recomputed_from_raw_ratings() -> None:
    document = _ready()
    document["pre_adjudication_agreement"]["exact_agreement_count"] = 4

    readiness = assess_severity_calibration(document)

    assert not readiness.ready
    assert any(
        "exact_agreement_count is inconsistent" in item
        for item in readiness.blockers
    )


def test_required_s2_s3_boundary_roles_cannot_be_omitted() -> None:
    document = _ready()
    document["anchor_reviews"][1]["expected_boundary_role"] = "clear_S2_anchor"

    readiness = assess_severity_calibration(document)

    assert not readiness.ready
    assert any("S2_S3_boundary" in item for item in readiness.blockers)


def test_major_threshold_levels_must_match_threshold_rule() -> None:
    document = _ready()
    document["major_threshold_decision"]["included_levels"] = ["S3"]

    readiness = assess_severity_calibration(document)

    assert not readiness.ready
    assert any("included_levels do not match" in item for item in readiness.blockers)


def test_completed_calibration_cannot_keep_indeterminate_adjudication() -> None:
    document = _ready()
    document["anchor_reviews"][0]["adjudicated_severity"] = "INDETERMINATE"

    readiness = assess_severity_calibration(document)

    assert not readiness.ready
    assert any(
        "cannot retain INDETERMINATE" in item
        for item in readiness.blockers
    )


def test_each_anchor_must_be_rated_by_exact_calibration_roster() -> None:
    document = deepcopy(_ready())
    document["anchor_reviews"][0]["reviewer_ratings"][1]["reviewer_id"] = "R-C"

    readiness = assess_severity_calibration(document)

    assert not readiness.ready
    assert any(
        "do not match calibration roster" in item
        for item in readiness.blockers
    )
