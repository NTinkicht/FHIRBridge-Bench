import yaml

_CANDIDATE_PATH = "contracts/review/relationship_candidates_v0.1.yaml"


def _candidates() -> dict:
    with open(_CANDIDATE_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_relationship_candidates_are_explicitly_non_scored_before_review() -> None:
    document = _candidates()
    candidates = document["candidates"]

    assert document["candidate_set"]["status"] == "external_review_required"
    assert document["candidate_set"]["parent_contract"]["version"] == "0.2.0"
    assert len(candidates) == 3
    assert len({item["candidate_rule_id"] for item in candidates}) == len(candidates)
    assert all(
        item["current_projectability"] == "INDETERMINATE"
        for item in candidates
    )


def test_misattribution_candidates_cover_report_and_specimen_context() -> None:
    document = _candidates()
    by_id = {
        item["candidate_rule_id"]: item for item in document["candidates"]
    }

    assert set(by_id) == {
        "REPORT_RESULT_MEMBERSHIP_001",
        "REPORT_SPECIMEN_MEMBERSHIP_001",
        "OBSERVATION_SPECIMEN_MEMBERSHIP_001",
    }
    assert all(
        item["candidate_failure_class_if_scored"] == "MISATTRIBUTION"
        for item in by_id.values()
    )
    assert all(item["candidate_severity"] == "S3" for item in by_id.values())
    assert all(item["external_review_questions"] for item in by_id.values())
