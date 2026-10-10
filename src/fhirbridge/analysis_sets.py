"""Deterministic construction of preregistered paired analysis sets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

_STRUCTURAL = frozenset(
    {"VALID", "INVALID", "MEASUREMENT_FAILURE", "POLICY_UNRESOLVED"}
)
_SEMANTIC = frozenset({"FAITHFUL", "UNFAITHFUL", "INDETERMINATE"})


@dataclass(frozen=True)
class ArmOutcome:
    structural_outcome: str
    semantic_verdict: str


@dataclass(frozen=True)
class PairedAnalysisSet:
    estimand: str
    arm_a: str
    arm_b: str
    case_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    outcome_a: tuple[int, ...]
    outcome_b: tuple[int, ...]
    excluded_case_count: int
    exclusion_counts: dict[str, int]


def _validate_outcome(outcome: ArmOutcome, *, label: str) -> None:
    if outcome.structural_outcome not in _STRUCTURAL:
        raise ValueError(
            f"{label} has unsupported structural outcome: "
            f"{outcome.structural_outcome}"
        )
    if outcome.semantic_verdict not in _SEMANTIC:
        raise ValueError(
            f"{label} has unsupported semantic verdict: "
            f"{outcome.semantic_verdict}"
        )


def _case_fields(row: dict[str, Any]) -> tuple[str, str]:
    case_id = row.get("case_id")
    cluster_id = row.get("cluster_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("each analysis row requires a non-empty case_id")
    if not isinstance(cluster_id, str) or not cluster_id:
        raise ValueError(f"{case_id}: cluster_id must be a non-empty string")
    return case_id, cluster_id


def _arm_outcome(
    row: dict[str, Any],
    arm_id: str,
    *,
    case_id: str,
) -> ArmOutcome:
    arms = row.get("arms")
    if not isinstance(arms, dict):
        raise ValueError(f"{case_id}: arms must be a mapping")
    raw = arms.get(arm_id)
    if not isinstance(raw, dict):
        raise ValueError(
            f"{case_id}: missing explicit attempted-transform outcome for {arm_id}"
        )
    outcome = ArmOutcome(
        structural_outcome=str(raw.get("structural_outcome")),
        semantic_verdict=str(raw.get("semantic_verdict")),
    )
    _validate_outcome(outcome, label=f"{case_id}/{arm_id}")
    return outcome


def _vur_exclusion_reason(
    outcome_a: ArmOutcome,
    outcome_b: ArmOutcome,
) -> str | None:
    if outcome_a.structural_outcome != "VALID":
        return f"arm_a_{outcome_a.structural_outcome.lower()}"
    if outcome_b.structural_outcome != "VALID":
        return f"arm_b_{outcome_b.structural_outcome.lower()}"
    if outcome_a.semantic_verdict == "INDETERMINATE":
        return "arm_a_semantic_indeterminate"
    if outcome_b.semantic_verdict == "INDETERMINATE":
        return "arm_b_semantic_indeterminate"
    return None


def build_paired_vur_set(
    rows: list[dict[str, Any]],
    *,
    arm_a: str,
    arm_b: str,
) -> PairedAnalysisSet:
    """Build the frozen paired VUR set.

    A case is included only when both arms are structurally VALID and both
    semantic verdicts are determinate. Missing arm attempts are errors rather
    than exclusions because system failures must be represented explicitly as
    MEASUREMENT_FAILURE.
    """

    if not rows:
        raise ValueError("analysis rows must not be empty")
    case_ids: list[str] = []
    cluster_ids: list[str] = []
    values_a: list[int] = []
    values_b: list[int] = []
    exclusions: Counter[str] = Counter()
    seen_cases: set[str] = set()

    for row in rows:
        case_id, cluster_id = _case_fields(row)
        if case_id in seen_cases:
            raise ValueError(f"duplicate analysis case_id: {case_id}")
        seen_cases.add(case_id)
        outcome_a = _arm_outcome(row, arm_a, case_id=case_id)
        outcome_b = _arm_outcome(row, arm_b, case_id=case_id)

        exclusion = _vur_exclusion_reason(outcome_a, outcome_b)
        if exclusion is not None:
            exclusions[exclusion] += 1
            continue

        case_ids.append(case_id)
        cluster_ids.append(cluster_id)
        values_a.append(int(outcome_a.semantic_verdict == "UNFAITHFUL"))
        values_b.append(int(outcome_b.semantic_verdict == "UNFAITHFUL"))

    return PairedAnalysisSet(
        estimand="VUR",
        arm_a=arm_a,
        arm_b=arm_b,
        case_ids=tuple(case_ids),
        cluster_ids=tuple(cluster_ids),
        outcome_a=tuple(values_a),
        outcome_b=tuple(values_b),
        excluded_case_count=sum(exclusions.values()),
        exclusion_counts=dict(sorted(exclusions.items())),
    )


def build_paired_vfy_set(
    rows: list[dict[str, Any]],
    *,
    arm_a: str,
    arm_b: str,
) -> PairedAnalysisSet:
    """Build the paired VFY set across all explicitly attempted transformations."""

    if not rows:
        raise ValueError("analysis rows must not be empty")
    case_ids: list[str] = []
    cluster_ids: list[str] = []
    values_a: list[int] = []
    values_b: list[int] = []
    seen_cases: set[str] = set()

    for row in rows:
        case_id, cluster_id = _case_fields(row)
        if case_id in seen_cases:
            raise ValueError(f"duplicate analysis case_id: {case_id}")
        seen_cases.add(case_id)
        outcome_a = _arm_outcome(row, arm_a, case_id=case_id)
        outcome_b = _arm_outcome(row, arm_b, case_id=case_id)

        case_ids.append(case_id)
        cluster_ids.append(cluster_id)
        values_a.append(
            int(
                outcome_a.structural_outcome == "VALID"
                and outcome_a.semantic_verdict == "FAITHFUL"
            )
        )
        values_b.append(
            int(
                outcome_b.structural_outcome == "VALID"
                and outcome_b.semantic_verdict == "FAITHFUL"
            )
        )

    return PairedAnalysisSet(
        estimand="VFY",
        arm_a=arm_a,
        arm_b=arm_b,
        case_ids=tuple(case_ids),
        cluster_ids=tuple(cluster_ids),
        outcome_a=tuple(values_a),
        outcome_b=tuple(values_b),
        excluded_case_count=0,
        exclusion_counts={},
    )
