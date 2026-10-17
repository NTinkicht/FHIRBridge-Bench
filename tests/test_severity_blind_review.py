from copy import deepcopy

import pytest
import yaml

from fhirbridge.severity_blind_review import (
    build_severity_adjudication_seed,
    paired_blind_severity_summary,
    validate_blind_severity_coverage,
)

_ANCHORS = "expert_validation/severity_anchor_set.yaml"


def _anchors() -> dict:
    with open(_ANCHORS, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _response(reviewer_id: str, *, mutate: dict[str, str] | None = None) -> dict:
    anchor_ids = [item["anchor_id"] for item in _anchors()["anchors"]]
    ratings = []
    for index, anchor_id in enumerate(anchor_ids):
        severity = ("S0", "S1", "S2", "S2", "S3", "S3")[index]
        if mutate and anchor_id in mutate:
            severity = mutate[anchor_id]
        ratings.append(
            {
                "anchor_id": anchor_id,
                "severity": severity,
                "rationale": f"Independent rationale for {anchor_id}.",
                "confidence": "MODERATE",
            }
        )
    return {
        "schema_version": "0.1.0",
        "assignment_id": "FHIRBRIDGE-SEVERITY-BLIND-001",
        "reviewer": {
            "reviewer_id": reviewer_id,
            "review_date": "2026-10-20",
            "expertise": ["laboratory clinical informatics"],
            "conflicts_of_interest": "None declared",
            "prior_project_involvement": "None",
        },
        "anchor_ratings": ratings,
        "attestation": {
            "independent_initial_ratings": True,
            "boundary_roles_hidden": True,
            "other_reviewer_ratings_hidden": True,
            "sealed_cases_not_used": True,
            "renderer_outputs_not_used_as_correctness_evidence": True,
        },
    }


def test_blind_severity_pair_reports_raw_agreement_before_adjudication() -> None:
    first = _response("R-A")
    second = _response("R-B", mutate={"SEV-A02": "S2"})

    summary = paired_blind_severity_summary(first, second, _anchors())

    assert summary.exact_agreement_count == 5
    assert summary.exact_agreement_rate == pytest.approx(5 / 6)
    assert summary.disagreement_anchor_ids == ("SEV-A02",)
    assert summary.disagreements[0].reviewer_a_severity == "S1"
    assert summary.disagreements[0].reviewer_b_severity == "S2"


def test_blind_severity_pair_requires_complete_anchor_coverage() -> None:
    response = _response("R-A")
    response["anchor_ratings"].pop()

    with pytest.raises(ValueError, match="complete anchor set"):
        validate_blind_severity_coverage(response, _anchors())


def test_blind_severity_pair_requires_distinct_reviewers() -> None:
    with pytest.raises(ValueError, match="distinct reviewer IDs"):
        paired_blind_severity_summary(
            _response("R-A"),
            _response("R-A"),
            _anchors(),
        )


def test_adjudication_seed_reveals_boundary_roles_only_post_blind() -> None:
    first = _response("R-A")
    second = _response("R-B", mutate={"SEV-A02": "S2"})

    seed = build_severity_adjudication_seed(
        first,
        second,
        _anchors(),
        candidate_policy_sha256="a" * 64,
        reviewer_a_response_sha256="b" * 64,
        reviewer_b_response_sha256="c" * 64,
    )

    assert seed["schema_version"] == "0.2.0"
    assert seed["blind_stage_evidence"] == {
        "assignment_id": "FHIRBRIDGE-SEVERITY-BLIND-001",
        "reviewer_a_response_sha256": "b" * 64,
        "reviewer_b_response_sha256": "c" * 64,
        "original_responses_retained": True,
        "boundary_roles_hidden_initially": True,
    }
    by_id = {item["anchor_id"]: item for item in seed["anchor_reviews"]}
    assert by_id["SEV-A02"]["expected_boundary_role"] == "S1_S2_boundary"
    assert by_id["SEV-A02"]["adjudicated_severity"] == "INDETERMINATE"
    assert "TO_BE_COMPLETED" in by_id["SEV-A02"]["adjudication_rationale"]


def test_adjudication_seed_does_not_mutate_blind_responses() -> None:
    first = _response("R-A")
    second = _response("R-B")
    original_first = deepcopy(first)
    original_second = deepcopy(second)

    build_severity_adjudication_seed(
        first,
        second,
        _anchors(),
        candidate_policy_sha256="a" * 64,
        reviewer_a_response_sha256="b" * 64,
        reviewer_b_response_sha256="c" * 64,
    )

    assert first == original_first
    assert second == original_second
