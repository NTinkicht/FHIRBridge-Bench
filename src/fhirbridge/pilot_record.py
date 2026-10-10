"""Deterministic builder for the pilot verifier-acceptance preregistration.

The builder computes measurement metrics from raw adjudicated expert labels and
tri-state verifier verdicts. Numeric acceptance thresholds remain explicit
caller inputs; this module never selects them from sealed evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .instrument_validation import qualify_instrument_with_abstention

_EXPERT = frozenset({"YES", "NO", "INDETERMINATE"})
_VERIFIER = frozenset({"FAITHFUL", "UNFAITHFUL", "INDETERMINATE"})


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _metric(interval: Any) -> dict[str, object]:
    return {
        "estimate": interval.estimate,
        "lower": interval.lower,
        "upper": interval.upper,
        "method": "Wilson_95_percent",
    }


def _by_case(
    items: list[dict[str, Any]],
    *,
    verdict_field: str,
    allowed: frozenset[str],
    label: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{label} items must be objects")
        case_id = item.get("case_id")
        verdict = item.get(verdict_field)
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label} item requires a non-empty case_id")
        if case_id in result:
            raise ValueError(f"duplicate {label} case_id: {case_id}")
        if verdict not in allowed:
            raise ValueError(
                f"{label} {case_id} has unsupported {verdict_field}: {verdict!r}"
            )
        result[case_id] = str(verdict)
    if not result:
        raise ValueError(f"{label} must not be empty")
    return result


def build_pilot_acceptance_record(
    *,
    adjudications: list[dict[str, Any]],
    verifier_results: list[dict[str, Any]],
    record_id: str,
    created_at: str,
    pilot_case_manifest_sha256: str,
    repository_commit: str,
    verifier_sha256: str,
    projectability_contract_sha256: str,
    minimum_sensitivity: float,
    sensitivity_statistic: str,
    sensitivity_rationale: str,
    minimum_ppv: float,
    ppv_statistic: str,
    ppv_rationale: str,
    maximum_runtime_indeterminate_rate: float,
    indeterminate_statistic: str,
    indeterminate_rationale: str,
    sampling_enrichment_or_weighting_notes: str | None = None,
) -> dict[str, Any]:
    """Build one preregistration record without silently dropping uncertainty."""

    expert_by_case = _by_case(
        adjudications,
        verdict_field="adjudicated_verdict",
        allowed=_EXPERT,
        label="adjudication",
    )
    verifier_by_case = _by_case(
        verifier_results,
        verdict_field="semantic_verdict",
        allowed=_VERIFIER,
        label="verifier result",
    )
    if set(expert_by_case) != set(verifier_by_case):
        raise ValueError(
            "adjudication and verifier case sets must match exactly; "
            f"missing_verifier={sorted(set(expert_by_case) - set(verifier_by_case))}, "
            f"unexpected_verifier={sorted(set(verifier_by_case) - set(expert_by_case))}"
        )

    case_ids = tuple(sorted(expert_by_case))
    expert_indeterminate = sum(
        expert_by_case[case_id] == "INDETERMINATE" for case_id in case_ids
    )
    determinate_ids = [
        case_id
        for case_id in case_ids
        if expert_by_case[case_id] != "INDETERMINATE"
    ]
    if not determinate_ids:
        raise ValueError("pilot contains no determinate adjudicated expert cases")

    expert_binary = [
        expert_by_case[case_id] == "YES" for case_id in determinate_ids
    ]
    verifier_verdicts = [
        verifier_by_case[case_id] for case_id in determinate_ids
    ]
    qualification = qualify_instrument_with_abstention(
        expert_binary,
        verifier_verdicts,
    )
    binary = qualification.determinate_binary
    counts = binary.counts

    positive_count = sum(expert_binary)
    negative_count = len(expert_binary) - positive_count
    adjudication_bundle_sha256 = _canonical_sha256(
        sorted(adjudications, key=lambda item: item["case_id"])
    )

    return {
        "schema_version": "0.4.0",
        "record_id": record_id,
        "status": "preregistered",
        "created_at": created_at,
        "pilot_evidence": {
            "pilot_case_manifest_sha256": pilot_case_manifest_sha256,
            "pilot_adjudication_bundle_sha256": adjudication_bundle_sha256,
            "case_count": len(case_ids),
            "expert_major_error_positive_count": positive_count,
            "expert_major_error_negative_count": negative_count,
            "expert_major_error_indeterminate_count": expert_indeterminate,
            "sampling_enrichment_or_weighting_notes": (
                sampling_enrichment_or_weighting_notes
            ),
        },
        "frozen_instrument": {
            "repository_commit": repository_commit,
            "verifier_sha256": verifier_sha256,
            "projectability_contract_sha256": projectability_contract_sha256,
        },
        "metrics": {
            "true_positive": counts.true_positive,
            "true_negative": counts.true_negative,
            "false_positive": counts.false_positive,
            "false_negative": counts.false_negative,
            "runtime_indeterminate_count": qualification.indeterminate_count,
            "runtime_indeterminate_expert_positive_count": (
                qualification.expert_positive_indeterminate_count
            ),
            "runtime_indeterminate_expert_negative_count": (
                qualification.expert_negative_indeterminate_count
            ),
            "runtime_indeterminate_rate": _metric(
                qualification.indeterminate_rate
            ),
            "sensitivity": _metric(qualification.effective_sensitivity),
            "specificity": _metric(qualification.effective_specificity),
            "ppv": _metric(binary.ppv),
            "npv": _metric(binary.npv),
            "accuracy": _metric(qualification.effective_accuracy),
        },
        "acceptance_gate": {
            "minimum_sensitivity": minimum_sensitivity,
            "sensitivity_statistic": sensitivity_statistic,
            "sensitivity_rationale": sensitivity_rationale,
            "minimum_ppv": minimum_ppv,
            "ppv_statistic": ppv_statistic,
            "ppv_rationale": ppv_rationale,
            "maximum_runtime_indeterminate_rate": (
                maximum_runtime_indeterminate_rate
            ),
            "indeterminate_statistic": indeterminate_statistic,
            "indeterminate_rationale": indeterminate_rationale,
        },
        "timing_attestation": {
            "sealed_set_opened": False,
            "thresholds_recorded_before_sealed_opening": True,
            "sealed_results_used_to_choose_thresholds": False,
        },
    }
