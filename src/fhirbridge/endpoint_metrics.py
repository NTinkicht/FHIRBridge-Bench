"""Primary endpoint summaries with explicit structural/semantic uncertainty."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

_VERDICTS = frozenset({"FAITHFUL", "UNFAITHFUL", "INDETERMINATE"})
_STRUCTURAL_OUTCOMES = frozenset(
    {"VALID", "INVALID", "MEASUREMENT_FAILURE", "POLICY_UNRESOLVED"}
)


@dataclass(frozen=True)
class VurSummary:
    attempted: int
    structurally_valid: int
    structurally_invalid: int
    measurement_failure: int
    policy_unresolved: int
    faithful: int
    unfaithful: int
    indeterminate: int
    determinate_denominator: int
    structural_validity_rate: float
    structural_invalidity_rate: float
    measurement_failure_rate: float
    policy_unresolved_rate: float
    valid_and_faithful_yield: float
    valid_and_unfaithful_yield: float
    valid_indeterminate_yield: float
    vur: float | None
    indeterminate_rate: float | None
    best_case_vur: float | None
    worst_case_vur: float | None


def summarize_endpoint_states(
    structural_outcomes: Iterable[str],
    semantic_verdicts: Iterable[str],
) -> VurSummary:
    """Summarize VUR/VFY without collapsing structural measurement states.

    Only VALID outputs may enter the VUR denominator. INVALID,
    MEASUREMENT_FAILURE, and POLICY_UNRESOLVED remain visible in all-attempt
    reporting and never become valid by default.
    """

    structural = list(structural_outcomes)
    verdicts = list(semantic_verdicts)
    if not structural:
        raise ValueError("structural_outcomes must not be empty")
    if len(structural) != len(verdicts):
        raise ValueError(
            "structural outcome and semantic verdict vectors must align"
        )

    invalid_structural = sorted(
        {value for value in structural if value not in _STRUCTURAL_OUTCOMES}
    )
    if invalid_structural:
        raise ValueError(
            f"unsupported structural outcome(s): {invalid_structural}"
        )

    invalid_verdicts = sorted(
        {value for value in verdicts if value not in _VERDICTS}
    )
    if invalid_verdicts:
        raise ValueError(f"unsupported semantic verdict(s): {invalid_verdicts}")

    valid_verdicts = [
        verdict
        for outcome, verdict in zip(structural, verdicts, strict=True)
        if outcome == "VALID"
    ]
    valid_count = len(valid_verdicts)
    invalid_count = structural.count("INVALID")
    measurement_failure = structural.count("MEASUREMENT_FAILURE")
    policy_unresolved = structural.count("POLICY_UNRESOLVED")

    faithful = valid_verdicts.count("FAITHFUL")
    unfaithful = valid_verdicts.count("UNFAITHFUL")
    indeterminate = valid_verdicts.count("INDETERMINATE")
    determinate = faithful + unfaithful

    attempted = len(structural)
    structural_validity_rate = valid_count / attempted
    structural_invalidity_rate = invalid_count / attempted
    measurement_failure_rate = measurement_failure / attempted
    policy_unresolved_rate = policy_unresolved / attempted
    valid_and_faithful_yield = faithful / attempted
    valid_and_unfaithful_yield = unfaithful / attempted
    valid_indeterminate_yield = indeterminate / attempted
    vur = unfaithful / determinate if determinate else None
    indeterminate_rate = indeterminate / valid_count if valid_count else None
    best_case = unfaithful / valid_count if valid_count else None
    worst_case = (
        (unfaithful + indeterminate) / valid_count
        if valid_count
        else None
    )

    return VurSummary(
        attempted=attempted,
        structurally_valid=valid_count,
        structurally_invalid=invalid_count,
        measurement_failure=measurement_failure,
        policy_unresolved=policy_unresolved,
        faithful=faithful,
        unfaithful=unfaithful,
        indeterminate=indeterminate,
        determinate_denominator=determinate,
        structural_validity_rate=structural_validity_rate,
        structural_invalidity_rate=structural_invalidity_rate,
        measurement_failure_rate=measurement_failure_rate,
        policy_unresolved_rate=policy_unresolved_rate,
        valid_and_faithful_yield=valid_and_faithful_yield,
        valid_and_unfaithful_yield=valid_and_unfaithful_yield,
        valid_indeterminate_yield=valid_indeterminate_yield,
        vur=vur,
        indeterminate_rate=indeterminate_rate,
        best_case_vur=best_case,
        worst_case_vur=worst_case,
    )


def summarize_vur(
    structural_validity: Iterable[bool],
    semantic_verdicts: Iterable[str],
) -> VurSummary:
    """Compatibility wrapper for legacy boolean structural-validity inputs."""

    structural = list(structural_validity)
    if not structural:
        raise ValueError("structural_validity must not be empty")
    if any(type(value) is not bool for value in structural):
        raise ValueError("structural_validity must contain booleans only")

    outcomes = ["VALID" if value else "INVALID" for value in structural]
    return summarize_endpoint_states(outcomes, semantic_verdicts)
