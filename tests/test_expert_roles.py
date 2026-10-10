import yaml

from fhirbridge.expert_roles import assess_reviewer_roster

_TEMPLATE = "expert_validation/examples/reviewer_roster_template.yaml"


def _template() -> dict:
    with open(_TEMPLATE, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _ready() -> dict:
    document = _template()
    document["roster_id"] = "ROSTER-001"
    document["status"] = "locked_preopening"
    document["created_at"] = "2026-10-20T10:00:00Z"
    for member in document["members"]:
        member["conflicts_of_interest"] = "None declared"
        member["prior_project_involvement"] = "None"
    document["members"][0]["member_id"] = "EXT-INTEROP-01"
    document["members"][1]["member_id"] = "EXT-CLINICAL-01"
    document["members"][2]["member_id"] = "EXT-ADJ-01"
    return document


def test_repository_roster_template_is_deliberately_not_ready() -> None:
    readiness = assess_reviewer_roster(_template())

    assert not readiness.ready
    assert any("not locked preopening" in blocker for blocker in readiness.blockers)
    assert any("placeholder" in blocker for blocker in readiness.blockers)
    assert any("disclosure is incomplete" in blocker for blocker in readiness.blockers)


def test_distinct_blinded_expert_roster_can_be_ready() -> None:
    readiness = assess_reviewer_roster(_ready())

    assert readiness.ready
    assert readiness.blockers == ()


def test_primary_reviewer_blinding_is_fail_closed() -> None:
    document = _ready()
    document["members"][0]["access"]["verifier_verdict"] = True

    readiness = assess_reviewer_roster(document)

    assert not readiness.ready
    assert any("verifier_verdict" in blocker for blocker in readiness.blockers)


def test_renderer_implementer_cannot_be_primary_output_reviewer() -> None:
    document = _ready()
    document["members"][1]["renderer_implementation_participation"] = True

    readiness = assess_reviewer_roster(document)

    assert not readiness.ready
    assert any(
        "participated in renderer implementation" in blocker
        for blocker in readiness.blockers
    )


def test_contract_reviewer_overlap_requires_analytical_separation() -> None:
    document = _ready()
    document["members"][0]["contract_review_participation"] = True
    document["members"][0]["analytical_separation_attested"] = False

    readiness = assess_reviewer_roster(document)

    assert not readiness.ready
    assert any("analytical separation" in blocker for blocker in readiness.blockers)


def test_adjudicator_must_be_distinct_from_primary_reviewers() -> None:
    document = _ready()
    document["members"][2]["member_id"] = document["members"][0]["member_id"]

    readiness = assess_reviewer_roster(document)

    assert not readiness.ready
    assert any("duplicate reviewer" in blocker for blocker in readiness.blockers)
    assert any("adjudicator must be distinct" in blocker for blocker in readiness.blockers)
