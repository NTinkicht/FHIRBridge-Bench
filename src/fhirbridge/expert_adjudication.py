"""Preserve blinded expert labels and create separate adjudication records.

Pre-adjudication reviewer labels are immutable inputs for reliability analysis.
Adjudication produces a separate record and never overwrites either reviewer's
original annotation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agreement import AgreementResult, agreement_statistics


@dataclass(frozen=True)
class TransformationDisagreement:
    case_id: str
    reviewer_a_id: str
    reviewer_b_id: str
    reviewer_a_verdict: str
    reviewer_b_verdict: str


@dataclass(frozen=True)
class ExpertPairSummary:
    case_ids: tuple[str, ...]
    reviewer_a_id: str
    reviewer_b_id: str
    agreement: AgreementResult
    disagreements: tuple[TransformationDisagreement, ...]


@dataclass(frozen=True)
class AdjudicatedCase:
    case_id: str
    reviewer_a_id: str
    reviewer_b_id: str
    reviewer_a_verdict: str
    reviewer_b_verdict: str
    adjudicator_id: str
    adjudicated_verdict: str
    rationale: str


def _reviewer_id(annotation: dict[str, Any]) -> str:
    reviewer = annotation.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("annotation must contain reviewer metadata")
    reviewer_id = reviewer.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        raise ValueError("reviewer.reviewer_id must be a non-empty string")
    return reviewer_id


def _case_id(annotation: dict[str, Any]) -> str:
    value = annotation.get("case_id")
    if not isinstance(value, str) or not value:
        raise ValueError("annotation.case_id must be a non-empty string")
    return value


def _verdict(annotation: dict[str, Any]) -> str:
    verdict = annotation.get("transformation_verdict")
    if not isinstance(verdict, dict):
        raise ValueError("annotation must contain transformation_verdict")
    value = verdict.get("major_semantic_error")
    if value not in {"YES", "NO", "INDETERMINATE"}:
        raise ValueError("major_semantic_error must be YES, NO, or INDETERMINATE")
    return value


def _by_case(annotations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for annotation in annotations:
        case_id = _case_id(annotation)
        if case_id in result:
            raise ValueError(f"duplicate expert annotation for case {case_id}")
        result[case_id] = annotation
    if not result:
        raise ValueError("at least one expert annotation is required")
    return result


def summarize_expert_pair(
    annotations_a: list[dict[str, Any]],
    annotations_b: list[dict[str, Any]],
) -> ExpertPairSummary:
    """Measure pre-adjudication agreement between two blinded reviewers."""

    a_by_case = _by_case(annotations_a)
    b_by_case = _by_case(annotations_b)
    if set(a_by_case) != set(b_by_case):
        raise ValueError("reviewer annotation sets must cover the same case IDs")

    reviewer_a_ids = {_reviewer_id(item) for item in a_by_case.values()}
    reviewer_b_ids = {_reviewer_id(item) for item in b_by_case.values()}
    if len(reviewer_a_ids) != 1 or len(reviewer_b_ids) != 1:
        raise ValueError("each annotation set must belong to exactly one reviewer")
    reviewer_a = next(iter(reviewer_a_ids))
    reviewer_b = next(iter(reviewer_b_ids))
    if reviewer_a == reviewer_b:
        raise ValueError("agreement requires two distinct reviewers")

    case_ids = tuple(sorted(a_by_case))
    labels_a = [_verdict(a_by_case[case_id]) for case_id in case_ids]
    labels_b = [_verdict(b_by_case[case_id]) for case_id in case_ids]
    agreement = agreement_statistics(labels_a, labels_b)
    disagreements = tuple(
        TransformationDisagreement(
            case_id=case_id,
            reviewer_a_id=reviewer_a,
            reviewer_b_id=reviewer_b,
            reviewer_a_verdict=_verdict(a_by_case[case_id]),
            reviewer_b_verdict=_verdict(b_by_case[case_id]),
        )
        for case_id in case_ids
        if _verdict(a_by_case[case_id]) != _verdict(b_by_case[case_id])
    )
    return ExpertPairSummary(
        case_ids=case_ids,
        reviewer_a_id=reviewer_a,
        reviewer_b_id=reviewer_b,
        agreement=agreement,
        disagreements=disagreements,
    )


def adjudicate_case(
    annotation_a: dict[str, Any],
    annotation_b: dict[str, Any],
    *,
    adjudicator_id: str,
    adjudicated_verdict: str,
    rationale: str,
) -> AdjudicatedCase:
    """Create a separate adjudication record without mutating raw annotations."""

    case_a = _case_id(annotation_a)
    case_b = _case_id(annotation_b)
    if case_a != case_b:
        raise ValueError("adjudication inputs must refer to the same case")
    reviewer_a = _reviewer_id(annotation_a)
    reviewer_b = _reviewer_id(annotation_b)
    if reviewer_a == reviewer_b:
        raise ValueError("adjudication requires two distinct primary reviewers")
    if not isinstance(adjudicator_id, str) or not adjudicator_id:
        raise ValueError("adjudicator_id must be a non-empty string")
    if adjudicator_id in {reviewer_a, reviewer_b}:
        raise ValueError("adjudicator must be distinct from primary reviewers")
    if adjudicated_verdict not in {"YES", "NO", "INDETERMINATE"}:
        raise ValueError("adjudicated_verdict must be YES, NO, or INDETERMINATE")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("adjudication rationale must be non-empty")

    return AdjudicatedCase(
        case_id=case_a,
        reviewer_a_id=reviewer_a,
        reviewer_b_id=reviewer_b,
        reviewer_a_verdict=_verdict(annotation_a),
        reviewer_b_verdict=_verdict(annotation_b),
        adjudicator_id=adjudicator_id,
        adjudicated_verdict=adjudicated_verdict,
        rationale=rationale,
    )
