"""Primary endpoint summaries with explicit indeterminate handling."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

_VERDICTS = frozenset({"FAITHFUL", "UNFAITHFUL", "INDETERMINATE"})


@dataclass(frozen=True)
class VurSummary:
    attempted: int
    structurally_valid: int
    structurally_invalid: int
    faithful: int
    unfaithful: int
    indeterminate: int
    determinate_denominator: int
    structural_validity_rate: float
    valid_and_faithful_yield: float
    valid_and_unfaithful_yield: float
    valid_indeterminate_yield: float
    vur: float | None
    indeterminate_rate: float | None
    best_case_vur: float | None
    worst_case_vur: float | None


def summarize_vur(
    structural_validity: Iterable[bool],
    semantic_verdicts: Iterable[str],
) -> VurSummary:
    """Summarize valid-but-unfaithful outcomes without hiding uncertainty.

    Semantic verdicts for structurally invalid outputs are retained in the input
    vector for alignment but do not enter VUR. Among structurally valid outputs,
    the point estimate uses determinate FAITHFUL/UNFAITHFUL cases only.
    INDETERMINATE cases are reported separately and define best/worst-case bounds.
    """

    structural = list(structural_validity)
    verdicts = list(semantic_verdicts)
    if not structural:
        raise ValueError("structural_validity must not be empty")
    if len(structural) != len(verdicts):
        raise ValueError("structural validity and semantic verdict vectors must align")
    if any(type(value) is not bool for value in structural):
        raise ValueError("structural_validity must contain booleans only")
    invalid_verdicts = sorted({value for value in verdicts if value not in _VERDICTS})
    if invalid_verdicts:
        raise ValueError(f"unsupported semantic verdict(s): {invalid_verdicts}")

    valid_verdicts = [
        verdict
        for is_valid, verdict in zip(structural, verdicts, strict=True)
        if is_valid
    ]
    valid_count = len(valid_verdicts)
    faithful = valid_verdicts.count("FAITHFUL")
    unfaithful = valid_verdicts.count("UNFAITHFUL")
    indeterminate = valid_verdicts.count("INDETERMINATE")
    determinate = faithful + unfaithful

    attempted = len(structural)
    structural_validity_rate = valid_count / attempted
    valid_and_faithful_yield = faithful / attempted
    valid_and_unfaithful_yield = unfaithful / attempted
    valid_indeterminate_yield = indeterminate / attempted
    vur = unfaithful / determinate if determinate else None
    indeterminate_rate = indeterminate / valid_count if valid_count else None
    best_case = unfaithful / valid_count if valid_count else None
    worst_case = (unfaithful + indeterminate) / valid_count if valid_count else None

    return VurSummary(
        attempted=attempted,
        structurally_valid=valid_count,
        structurally_invalid=len(structural) - valid_count,
        faithful=faithful,
        unfaithful=unfaithful,
        indeterminate=indeterminate,
        determinate_denominator=determinate,
        structural_validity_rate=structural_validity_rate,
        valid_and_faithful_yield=valid_and_faithful_yield,
        valid_and_unfaithful_yield=valid_and_unfaithful_yield,
        valid_indeterminate_yield=valid_indeterminate_yield,
        vur=vur,
        indeterminate_rate=indeterminate_rate,
        best_case_vur=best_case,
        worst_case_vur=worst_case,
    )
