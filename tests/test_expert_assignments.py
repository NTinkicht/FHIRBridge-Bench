import yaml

from fhirbridge.expert_assignments import assess_case_assignment_manifest

_ASSIGNMENT_TEMPLATE = (
    "expert_validation/examples/case_assignment_manifest_template.yaml"
)
_ROSTER_TEMPLATE = "expert_validation/examples/reviewer_roster_template.yaml"


def _yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _ready_roster() -> dict:
    roster = _yaml(_ROSTER_TEMPLATE)
    roster["roster_id"] = "ROSTER-001"
    roster["status"] = "locked_preopening"
    roster["created_at"] = "2026-10-20T10:00:00Z"
    roster["members"][0]["member_id"] = "R-INT"
    roster["members"][1]["member_id"] = "R-CLIN"
    roster["members"][2]["member_id"] = "R-ADJ"
    for member in roster["members"]:
        member["conflicts_of_interest"] = "None declared"
        member["prior_project_involvement"] = "None"
    return roster


def _ready_assignment() -> dict:
    assignment = _yaml(_ASSIGNMENT_TEMPLATE)
    assignment["assignment_id"] = "ASSIGN-001"
    assignment["status"] = "locked_preopening"
    assignment["created_at"] = "2026-10-20T11:00:00Z"
    assignment["reviewer_roster_id"] = "ROSTER-001"
    assignment["reviewer_roster_sha256"] = "1" * 64
    assignment["sealed_case_manifest_sha256"] = "2" * 64
    assignment["assignments"] = [
        {
            "case_id": "CASE-001",
            "primary_reviewer_ids": ["R-INT", "R-CLIN"],
        },
        {
            "case_id": "CASE-002",
            "primary_reviewer_ids": ["R-INT", "R-CLIN"],
        },
    ]
    return assignment


def test_repository_case_assignment_template_is_not_ready() -> None:
    readiness = assess_case_assignment_manifest(
        _yaml(_ASSIGNMENT_TEMPLATE),
        _ready_roster(),
    )

    assert not readiness.ready
    assert any("not locked preopening" in blocker for blocker in readiness.blockers)
    assert any("placeholder" in blocker for blocker in readiness.blockers)


def test_two_distinct_qualified_primary_reviewers_can_cover_each_case() -> None:
    readiness = assess_case_assignment_manifest(
        _ready_assignment(),
        _ready_roster(),
        expected_case_ids={"CASE-001", "CASE-002"},
    )

    assert readiness.ready
    assert readiness.blockers == ()


def test_case_pair_must_cover_interoperability_and_clinical_expertise() -> None:
    roster = _ready_roster()
    second_interop = {
        **roster["members"][0],
        "member_id": "R-INT-2",
    }
    roster["members"].append(second_interop)
    assignment = _ready_assignment()
    assignment["assignments"][0]["primary_reviewer_ids"] = ["R-INT", "R-INT-2"]

    readiness = assess_case_assignment_manifest(assignment, roster)

    assert not readiness.ready
    assert any("clinical_informatics_laboratory" in blocker for blocker in readiness.blockers)


def test_adjudicator_or_unknown_person_cannot_be_primary_case_reviewer() -> None:
    assignment = _ready_assignment()
    assignment["assignments"][0]["primary_reviewer_ids"] = ["R-INT", "R-ADJ"]

    readiness = assess_case_assignment_manifest(assignment, _ready_roster())

    assert not readiness.ready
    assert any("not an eligible primary reviewer" in blocker for blocker in readiness.blockers)


def test_expected_case_set_must_match_exactly() -> None:
    readiness = assess_case_assignment_manifest(
        _ready_assignment(),
        _ready_roster(),
        expected_case_ids={"CASE-001", "CASE-003"},
    )

    assert not readiness.ready
    assert any("CASE-003" in blocker for blocker in readiness.blockers)
    assert any("CASE-002" in blocker for blocker in readiness.blockers)
