"""Scientific readiness checks for pilot-derived acceptance preregistration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = (
    "TO_BE_",
    "TO-BE-",
    "TO BE ",
)


@dataclass(frozen=True)
class PilotAcceptanceReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _zero_hash(value: Any) -> bool:
    return isinstance(value, str) and value and set(value.lower()) <= {"0"}


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def assess_pilot_acceptance_preregistration(
    document: dict[str, Any],
) -> PilotAcceptanceReadiness:
    """Fail closed until a real pilot-derived gate is recorded."""

    blockers: list[str] = []

    if document.get("status") != "preregistered":
        blockers.append("pilot acceptance record is not marked preregistered")
    if document.get("created_at") is None:
        blockers.append("pilot acceptance record has no creation timestamp")

    pilot = document.get("pilot_evidence", {})
    if not isinstance(pilot, dict):
        blockers.append("pilot_evidence is missing")
        pilot = {}
    for key in (
        "pilot_case_manifest_sha256",
        "pilot_adjudication_bundle_sha256",
    ):
        value = pilot.get(key)
        if _zero_hash(value):
            blockers.append(f"{key} is still a zero placeholder")

    instrument = document.get("frozen_instrument", {})
    if not isinstance(instrument, dict):
        blockers.append("frozen_instrument is missing")
        instrument = {}
    for key in ("verifier_sha256", "projectability_contract_sha256"):
        if _zero_hash(instrument.get(key)):
            blockers.append(f"{key} is still a zero placeholder")
    repository_commit = instrument.get("repository_commit")
    if _zero_hash(repository_commit):
        blockers.append("repository_commit is still a zero placeholder")

    metrics = document.get("metrics", {})
    if not isinstance(metrics, dict):
        blockers.append("metrics are missing")
        metrics = {}
    count_keys = (
        "true_positive",
        "true_negative",
        "false_positive",
        "false_negative",
    )
    counts: list[int] = []
    for key in count_keys:
        value = metrics.get(key)
        if not isinstance(value, int) or value < 0:
            blockers.append(f"{key} must be a nonnegative integer")
        else:
            counts.append(value)
    case_count = pilot.get("case_count")
    if (
        len(counts) == len(count_keys)
        and isinstance(case_count, int)
        and sum(counts) != case_count
    ):
        blockers.append("pilot confusion counts do not sum to case_count")

    positive_count = pilot.get("expert_major_error_positive_count")
    negative_count = pilot.get("expert_major_error_negative_count")
    if isinstance(case_count, int) and all(
        isinstance(value, int) for value in (positive_count, negative_count)
    ):
        if positive_count + negative_count != case_count:
            blockers.append(
                "expert positive/negative counts do not sum to case_count"
            )

    for metric_name in ("sensitivity", "specificity", "ppv", "npv", "accuracy"):
        metric = metrics.get(metric_name)
        if not isinstance(metric, dict):
            blockers.append(f"{metric_name} metric is missing")
            continue
        estimate = metric.get("estimate")
        lower = metric.get("lower")
        upper = metric.get("upper")
        if not all(isinstance(value, (int, float)) for value in (estimate, lower, upper)):
            blockers.append(f"{metric_name} interval is incomplete")
            continue
        if not 0 <= lower <= estimate <= upper <= 1:
            blockers.append(f"{metric_name} interval is not ordered in [0,1]")
        if metric.get("method") != "Wilson_95_percent":
            blockers.append(f"{metric_name} does not use Wilson_95_percent")

    gate = document.get("acceptance_gate", {})
    if not isinstance(gate, dict):
        blockers.append("acceptance_gate is missing")
        gate = {}
    for name in ("minimum_sensitivity", "minimum_ppv"):
        value = gate.get(name)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            blockers.append(f"{name} must be numeric in [0,1]")
    for name in ("sensitivity_rationale", "ppv_rationale"):
        value = gate.get(name)
        if not isinstance(value, str) or not value.strip() or _placeholder(value):
            blockers.append(f"{name} is missing or still a placeholder")

    timing = document.get("timing_attestation", {})
    if not isinstance(timing, dict):
        blockers.append("timing_attestation is missing")
    else:
        if timing.get("sealed_set_opened") is not False:
            blockers.append("sealed set must still be unopened")
        if timing.get("thresholds_recorded_before_sealed_opening") is not True:
            blockers.append("thresholds are not attested as preregistered")
        if timing.get("sealed_results_used_to_choose_thresholds") is not False:
            blockers.append("sealed results must not be used to choose thresholds")

    return PilotAcceptanceReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
