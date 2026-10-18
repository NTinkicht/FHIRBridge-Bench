"""Prospective-manifest accounting for candidate Path B G0/G1 outcomes.

Development diagnostics only. No rule here qualifies the G1 validator,
freezes a primary estimand, or authorizes sealed confirmatory inference.
The expected assignments MUST come from a separate pre-run manifest and
cannot be reconstructed from the observed data after execution.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

_OUTCOMES = (
    "INVALID_G0",
    "INVALID_G1",
    "VALID_G1_FAITHFUL",
    "VALID_G1_UNFAITHFUL",
    "VALID_G1_SEMANTIC_INDETERMINATE",
    "STRUCTURAL_MEASUREMENT_FAILURE",
    "STRUCTURAL_POLICY_UNRESOLVED",
)
_OUTCOME_SET = frozenset(_OUTCOMES)
_ID_FIELDS = frozenset(
    {"source_instance_id", "model_key", "strategy", "analysis_cluster_id"}
)
_MANIFEST_FIELDS = _ID_FIELDS
_OBSERVED_FIELDS = _ID_FIELDS | {"outcome"}


@dataclass(frozen=True)
class ArmCensus:
    model_key: str
    strategy: str
    all_attempts: int
    counts_by_state: tuple[tuple[str, int], ...]
    vfy_g1_all_attempts: float
    valid_unfaithful_yield_g1_all_attempts: float
    descriptive_vur_g1: float | None


@dataclass(frozen=True)
class PairedVfyCensus:
    model_key: str
    arm_a: str
    arm_b: str
    all_paired_assignments: int
    both_vfy: int
    a_only_vfy: int
    b_only_vfy: int
    neither_vfy: int


@dataclass(frozen=True)
class PathBOutcomeAudit:
    manifest_sha256: str
    observed_sha256: str
    expected_assignment_count: int
    accounted_assignment_count: int
    arm_censuses: tuple[ArmCensus, ...]
    paired_vfy_censuses: tuple[PairedVfyCensus, ...]

    @property
    def status(self) -> str:
        return "PREFREEZE_SYNTHETIC_ANALYSIS_ONLY"

    @property
    def approved_confirmatory_estimand(self) -> bool:
        return False

    @property
    def G1_qualified(self) -> bool:
        return False

    @property
    def confirmatory_permission(self) -> bool:
        return False


def _digest(value: list[dict[str, str]]) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _identity(row: dict[str, str]) -> tuple[str, str, str]:
    return (row["source_instance_id"], row["model_key"], row["strategy"])


def _validate_row(row: Any, *, observed: bool) -> None:
    fields = _OBSERVED_FIELDS if observed else _MANIFEST_FIELDS
    if type(row) is not dict or set(row) != fields:
        raise ValueError("Path B assignment has missing or additional fields")
    if any(
        type(row[key]) is not str
        or not row[key].strip()
        or row[key] != row[key].strip()
        for key in fields
    ):
        raise ValueError("Path B assignment identifiers must be nonblank canonical strings")
    if observed and row["outcome"] not in _OUTCOME_SET:
        raise ValueError("Path B outcome is not an approved candidate partition state")


def audit_path_b_all_attempts(
    manifest: list[dict[str, str]],
    observations: list[dict[str, str]],
) -> PathBOutcomeAudit:
    """Report only complete, model-specific candidate descriptive quantities.

    A missing outcome is not excluded from the denominator. Rather, the
    *entire audit* fails until the data steward explicitly records its
    measurement failure or other proper predeclared outcome. No silently
    selected "both arms valid" subset is used for paired VFY.
    """
    if (
        type(manifest) is not list
        or type(observations) is not list
        or not manifest
    ):
        raise ValueError("nonempty independently declared manifest and observed list required")

    planned: dict[tuple[str, str, str], dict[str, str]] = {}
    cluster_by_case: dict[str, str] = {}
    for row in manifest:
        _validate_row(row, observed=False)
        key = _identity(row)
        if key in planned:
            raise ValueError("duplicate expected model/strategy/source assignment")
        planned[key] = row
        source = row["source_instance_id"]
        cluster = row["analysis_cluster_id"]
        if source in cluster_by_case and cluster_by_case[source] != cluster:
            raise ValueError("one source instance cannot change its analysis cluster")
        cluster_by_case[source] = cluster

    seen: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in observations:
        _validate_row(row, observed=True)
        key = _identity(row)
        if key in seen:
            raise ValueError("duplicate observed model/strategy/source assignment")
        if key not in planned:
            raise ValueError("unplanned outcome assignment cannot inflate denominator")
        if row["analysis_cluster_id"] != planned[key]["analysis_cluster_id"]:
            raise ValueError("observed cluster differs from the prospective manifest")
        seen[key] = row
    if set(seen) != set(planned):
        missing = len(set(planned) - set(seen))
        raise ValueError(f"{missing} prospectively expected assignments have no outcome")

    # This study compares paired strategies on identical inputs within each
    # model. Never compute a paired contrast on different observed case sets.
    source_by_arm: dict[tuple[str, str], set[str]] = defaultdict(set)
    cases_by_arm: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in observations:
        key = (row["model_key"], row["strategy"])
        source = row["source_instance_id"]
        source_by_arm[key].add(source)
        cases_by_arm[key][source] = row["outcome"]
    by_model: dict[str, list[str]] = defaultdict(list)
    for model, strategy in source_by_arm:
        by_model[model].append(strategy)

    pairs: list[PairedVfyCensus] = []
    for model in sorted(by_model):
        arms = sorted(by_model[model])
        if len(arms) > 1:
            reference = source_by_arm[model, arms[0]]
            if any(source_by_arm[model, arm] != reference for arm in arms[1:]):
                raise ValueError("incomplete crossed design: model strategies differ in cases")
        for a, b in itertools.combinations(arms, 2):
            counts = Counter(
                (
                    cases_by_arm[model, a][source] == "VALID_G1_FAITHFUL",
                    cases_by_arm[model, b][source] == "VALID_G1_FAITHFUL",
                )
                for source in sorted(source_by_arm[model, a])
            )
            pairs.append(
                PairedVfyCensus(
                    model_key=model,
                    arm_a=a,
                    arm_b=b,
                    all_paired_assignments=len(source_by_arm[model, a]),
                    both_vfy=counts[True, True],
                    a_only_vfy=counts[True, False],
                    b_only_vfy=counts[False, True],
                    neither_vfy=counts[False, False],
                )
            )

    arms: list[ArmCensus] = []
    for model, strategy in sorted(source_by_arm):
        group = Counter(cases_by_arm[model, strategy].values())
        n = sum(group.values())
        faithful = group["VALID_G1_FAITHFUL"]
        unfaithful = group["VALID_G1_UNFAITHFUL"]
        arms.append(
            ArmCensus(
                model_key=model,
                strategy=strategy,
                all_attempts=n,
                counts_by_state=tuple((s, group[s]) for s in _OUTCOMES),
                vfy_g1_all_attempts=faithful / n,
                valid_unfaithful_yield_g1_all_attempts=unfaithful / n,
                descriptive_vur_g1=(
                    unfaithful / (faithful + unfaithful)
                    if faithful + unfaithful else None
                ),
            )
        )

    return PathBOutcomeAudit(
        manifest_sha256=_digest(manifest),
        observed_sha256=_digest(observations),
        expected_assignment_count=len(planned),
        accounted_assignment_count=len(seen),
        arm_censuses=tuple(arms),
        paired_vfy_censuses=tuple(pairs),
    )
