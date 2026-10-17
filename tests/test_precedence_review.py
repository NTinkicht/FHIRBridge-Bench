import yaml

from fhirbridge.precedence_review import assess_precedence_review

_TEMPLATE = "expert_validation/examples/precedence_review_template.yaml"


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _ready(decision_a: str = "ACCEPT", decision_b: str = "ACCEPT") -> dict:
    document = _template()
    document["review_id"] = "PRECEDENCE-REVIEW-001"
    document["status"] = "completed"
    document["created_at"] = "2026-10-20T19:00:00Z"
    document["candidate_policy_sha256"] = "a" * 64
    document["blind_stage_evidence"] = {
        "assignment_id": "FHIRBRIDGE-PRECEDENCE-BLIND-001",
        "reviewer_a_response_sha256": "b" * 64,
        "reviewer_b_response_sha256": "c" * 64,
        "original_responses_retained": True,
        "other_reviewer_decisions_hidden_initially": True,
    }
    document["reviewers"] = [
        {
            "reviewer_id": "R-A",
            "expertise": ["HL7 interoperability"],
            "conflicts_of_interest": "None declared",
            "prior_project_involvement": "None",
        },
        {
            "reviewer_id": "R-B",
            "expertise": ["clinical informatics"],
            "conflicts_of_interest": "None declared",
            "prior_project_involvement": "None",
        },
    ]
    document["independent_decisions"] = [
        {
            "reviewer_id": "R-A",
            "decision": decision_a,
            "rationale": "Independent review A.",
        },
        {
            "reviewer_id": "R-B",
            "decision": decision_b,
            "rationale": "Independent review B.",
        },
    ]
    document["adjudication"] = {
        "decision": "ACCEPT",
        "rationale": "Consensus supports the candidate order.",
    }
    return document


def test_repository_precedence_review_template_is_not_complete() -> None:
    readiness = assess_precedence_review(_template())

    assert not readiness.complete
    assert not readiness.accepted
    assert any("not marked completed" in item for item in readiness.blockers)
    assert any("placeholder" in item for item in readiness.blockers)


def test_completed_accepted_precedence_review_can_be_ready() -> None:
    readiness = assess_precedence_review(_ready())

    assert readiness.complete
    assert readiness.accepted
    assert readiness.initial_agreement is True
    assert readiness.blockers == ()


def test_initial_disagreement_is_retained_but_can_be_adjudicated() -> None:
    readiness = assess_precedence_review(_ready("ACCEPT", "REJECT"))

    assert readiness.complete
    assert readiness.accepted
    assert readiness.initial_agreement is False


def test_completed_review_cannot_remain_indeterminate() -> None:
    document = _ready()
    document["adjudication"]["decision"] = "INDETERMINATE"

    readiness = assess_precedence_review(document)

    assert not readiness.complete
    assert any("cannot remain INDETERMINATE" in item for item in readiness.blockers)


def test_review_reject_decision_is_complete_but_not_accepted() -> None:
    document = _ready()
    document["adjudication"] = {
        "decision": "REJECT",
        "rationale": "Candidate order needs revision.",
    }

    readiness = assess_precedence_review(document)

    assert readiness.complete
    assert not readiness.accepted


def test_decisions_must_match_declared_reviewer_roster() -> None:
    document = _ready()
    document["independent_decisions"][1]["reviewer_id"] = "R-C"

    readiness = assess_precedence_review(document)

    assert not readiness.complete
    assert any("do not match" in item for item in readiness.blockers)


def test_completed_precedence_review_requires_response_hashes() -> None:
    document = _ready()
    document["blind_stage_evidence"]["reviewer_b_response_sha256"] = "0" * 64

    readiness = assess_precedence_review(document)

    assert not readiness.complete
    assert any(
        "reviewer_b_response_sha256" in item
        for item in readiness.blockers
    )


def test_completed_precedence_review_requires_hidden_initial_decisions() -> None:
    document = _ready()
    document["blind_stage_evidence"][
        "other_reviewer_decisions_hidden_initially"
    ] = False

    readiness = assess_precedence_review(document)

    assert not readiness.complete
    assert any(
        "were not hidden initially" in item
        for item in readiness.blockers
    )
