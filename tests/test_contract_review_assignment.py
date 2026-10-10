import fhirbridge.schema_validation
from fhirbridge.contract_review_assignment import build_contract_review_assignment

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"
_CANDIDATES = "contracts/review/relationship_candidates_v0.1.yaml"


def _assignment(stage: str = "blind") -> dict:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    candidates = fhirbridge.schema_validation.load_yaml(_CANDIDATES)
    return build_contract_review_assignment(contract, candidates, stage=stage)


def test_review_assignment_contains_every_required_item_once() -> None:
    assignment = _assignment()

    assert assignment["review_item_count"] == len(assignment["review_item_ids"])
    assert assignment["review_item_count"] == len(assignment["items"])
    assert len(set(assignment["review_item_ids"])) == assignment["review_item_count"]
    assert {item["rule_id"] for item in assignment["items"]} == set(
        assignment["review_item_ids"]
    )


def test_review_assignment_contains_no_human_decisions_or_model_evidence() -> None:
    assignment = _assignment()

    assert assignment["human_decisions_included"] is False
    assert assignment["review_independence"]["model_outputs_permitted"] is False
    assert assignment["review_independence"]["verifier_outputs_permitted"] is False
    assert (
        assignment["review_independence"][
            "renderer_outputs_permitted_as_correctness_evidence"
        ]
        is False
    )
    assert len(assignment["assignment_sha256"]) == 64


def test_review_assignment_includes_subject_attribution_candidate() -> None:
    assignment = _assignment("unblinded")
    item = next(
        item
        for item in assignment["items"]
        if item["rule_id"] == "OBSERVATION_SUBJECT_ATTRIBUTION_001"
    )

    assert item["review_item_type"] == "relationship_candidate"
    assert item["canonical_relation"] == "observation.subject_ref"
    assert item["proposed_projectability"] == "INDETERMINATE"
    assert item["proposed_failure_types"] == ["MISATTRIBUTION"]
    assert item["proposed_severity"] == "S3"


def test_blind_review_assignment_withholds_study_proposals() -> None:
    assignment = _assignment()
    item = next(
        item
        for item in assignment["items"]
        if item["rule_id"] == "OBSERVATION_SUBJECT_ATTRIBUTION_001"
    )

    assert assignment["review_stage"] == "blind"
    assert assignment["proposal_disclosure"] == (
        "withheld_for_independent_initial_classification"
    )
    assert "target_semantics" not in item
    assert "proposed_projectability" not in item
    assert "proposed_allowed_operations" not in item
    assert "proposed_failure_types" not in item
    assert "proposed_severity" not in item


def test_unblinded_review_requires_prior_blind_response_retention() -> None:
    assignment = _assignment("unblinded")

    assert assignment["review_stage"] == "unblinded"
    assert assignment["review_independence"][
        "blind_response_must_be_retained_before_unblinding"
    ] is True


def test_invalid_review_stage_is_rejected() -> None:
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT)
    candidates = fhirbridge.schema_validation.load_yaml(_CANDIDATES)

    try:
        build_contract_review_assignment(contract, candidates, stage="anchored")
    except ValueError as exc:
        assert "blind" in str(exc)
    else:
        raise AssertionError("invalid review stage was accepted")
