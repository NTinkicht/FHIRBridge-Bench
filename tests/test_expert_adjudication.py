import pytest

from fhirbridge.expert_adjudication import adjudicate_case, summarize_expert_pair


def _annotation(case_id: str, reviewer_id: str, verdict: str) -> dict:
    return {
        "case_id": case_id,
        "reviewer": {"reviewer_id": reviewer_id},
        "transformation_verdict": {"major_semantic_error": verdict},
    }


def test_pair_summary_uses_only_pre_adjudication_labels() -> None:
    reviewer_a = [
        _annotation("CASE-001", "REV-A", "YES"),
        _annotation("CASE-002", "REV-A", "NO"),
        _annotation("CASE-003", "REV-A", "NO"),
    ]
    reviewer_b = [
        _annotation("CASE-001", "REV-B", "YES"),
        _annotation("CASE-002", "REV-B", "YES"),
        _annotation("CASE-003", "REV-B", "NO"),
    ]

    summary = summarize_expert_pair(reviewer_a, reviewer_b)

    assert summary.agreement.n == 3
    assert summary.agreement.raw_agreement == pytest.approx(2 / 3)
    assert len(summary.disagreements) == 1
    assert summary.disagreements[0].case_id == "CASE-002"
    assert summary.disagreements[0].reviewer_a_verdict == "NO"
    assert summary.disagreements[0].reviewer_b_verdict == "YES"


def test_adjudication_creates_separate_record_without_mutating_raw_labels() -> None:
    annotation_a = _annotation("CASE-002", "REV-A", "NO")
    annotation_b = _annotation("CASE-002", "REV-B", "YES")

    adjudicated = adjudicate_case(
        annotation_a,
        annotation_b,
        adjudicator_id="REV-C",
        adjudicated_verdict="YES",
        rationale="The missing required laboratory fact is clinically meaningful.",
    )

    assert adjudicated.case_id == "CASE-002"
    assert adjudicated.reviewer_a_verdict == "NO"
    assert adjudicated.reviewer_b_verdict == "YES"
    assert adjudicated.adjudicated_verdict == "YES"
    assert annotation_a["transformation_verdict"]["major_semantic_error"] == "NO"
    assert annotation_b["transformation_verdict"]["major_semantic_error"] == "YES"


def test_pair_summary_requires_same_case_set() -> None:
    reviewer_a = [_annotation("CASE-001", "REV-A", "YES")]
    reviewer_b = [_annotation("CASE-002", "REV-B", "YES")]

    with pytest.raises(ValueError, match="same case IDs"):
        summarize_expert_pair(reviewer_a, reviewer_b)


def test_pair_summary_rejects_same_reviewer() -> None:
    reviewer_a = [_annotation("CASE-001", "REV-A", "YES")]
    reviewer_b = [_annotation("CASE-001", "REV-A", "NO")]

    with pytest.raises(ValueError, match="distinct reviewers"):
        summarize_expert_pair(reviewer_a, reviewer_b)


def test_adjudicator_must_be_independent() -> None:
    annotation_a = _annotation("CASE-001", "REV-A", "YES")
    annotation_b = _annotation("CASE-001", "REV-B", "NO")

    with pytest.raises(ValueError, match="distinct from primary reviewers"):
        adjudicate_case(
            annotation_a,
            annotation_b,
            adjudicator_id="REV-A",
            adjudicated_verdict="YES",
            rationale="Independent rationale placeholder.",
        )


def test_indeterminate_verdict_is_retained_not_forced() -> None:
    annotation_a = _annotation("CASE-004", "REV-A", "INDETERMINATE")
    annotation_b = _annotation("CASE-004", "REV-B", "YES")

    adjudicated = adjudicate_case(
        annotation_a,
        annotation_b,
        adjudicator_id="REV-C",
        adjudicated_verdict="INDETERMINATE",
        rationale="The frozen contract does not resolve this representation ambiguity.",
    )

    assert adjudicated.adjudicated_verdict == "INDETERMINATE"
