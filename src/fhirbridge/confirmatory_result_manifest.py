"""Readiness and cross-record checks for confirmatory result manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_TOKENS = ("TO_BE_", "TO-BE-", "TO BE ")


@dataclass(frozen=True)
class ConfirmatoryResultReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(token in upper for token in _PLACEHOLDER_TOKENS)


def _zeroish(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and set(value.lower()) <= {"0"}


def _artifact_blockers(
    artifact: Any,
    *,
    label: str,
    blockers: list[str],
) -> None:
    if not isinstance(artifact, dict):
        blockers.append(f"{label} is missing")
        return
    ref = artifact.get("path_or_ref")
    digest = artifact.get("sha256")
    if not isinstance(ref, str) or not ref or _placeholder(ref):
        blockers.append(f"{label}.path_or_ref is missing or placeholder")
    if not isinstance(digest, str) or len(digest) != 64 or _zeroish(digest):
        blockers.append(f"{label}.sha256 is missing or placeholder")


def assess_confirmatory_result_manifest(
    document: dict[str, Any],
    *,
    run_plan: dict[str, Any],
    run_plan_sha256: str,
) -> ConfirmatoryResultReadiness:
    """Validate immutable execution-to-analysis provenance against the run plan."""

    blockers: list[str] = []

    if document.get("status") != "execution_complete_audited":
        blockers.append("result manifest is not execution_complete_audited")
    if document.get("created_at") is None:
        blockers.append("result manifest has no creation timestamp")
    if _placeholder(document.get("result_manifest_id")):
        blockers.append("result_manifest_id is still a placeholder")
    if _zeroish(document.get("repository_commit")):
        blockers.append("repository_commit is still a zero placeholder")

    if document.get("run_plan_sha256") != run_plan_sha256:
        blockers.append("result manifest run_plan_sha256 does not match run plan")

    sealed_plan = run_plan.get("sealed_set")
    if not isinstance(sealed_plan, dict):
        blockers.append("run plan sealed_set binding is missing")
        sealed_plan = {}
    if document.get("sealed_bundle_sha256") != sealed_plan.get("bundle_sha256"):
        blockers.append("result manifest sealed bundle hash does not match run plan")

    model_keys = run_plan.get("model_keys")
    if not isinstance(model_keys, list) or not model_keys:
        blockers.append("run plan model_keys are missing")
        model_count = 0
    else:
        model_count = len(model_keys)
    case_count = sealed_plan.get("case_count")
    if not isinstance(case_count, int) or isinstance(case_count, bool) or case_count < 1:
        blockers.append("run plan case_count is invalid")
        case_count = 0

    raw = document.get("raw_execution_records")
    baseline = document.get("deterministic_baseline_outputs")
    audit = document.get("execution_audit")
    analysis = document.get("analysis_ready_dataset")
    _artifact_blockers(raw, label="raw_execution_records", blockers=blockers)
    _artifact_blockers(
        baseline,
        label="deterministic_baseline_outputs",
        blockers=blockers,
    )
    _artifact_blockers(audit, label="execution_audit", blockers=blockers)
    _artifact_blockers(
        analysis,
        label="analysis_ready_dataset",
        blockers=blockers,
    )

    if isinstance(audit, dict) and audit.get("complete") is not True:
        blockers.append("execution audit is not complete")

    if case_count and model_count:
        expected_raw = case_count * model_count * 3
        expected_baseline = case_count
        expected_analysis_rows = case_count * model_count
        if isinstance(raw, dict) and raw.get("record_count") != expected_raw:
            blockers.append(
                "raw_execution_records.record_count does not equal 3*N*M"
            )
        if (
            isinstance(baseline, dict)
            and baseline.get("record_count") != expected_baseline
        ):
            blockers.append(
                "deterministic_baseline_outputs.record_count does not equal N"
            )
        if (
            isinstance(analysis, dict)
            and analysis.get("record_count") != expected_analysis_rows
        ):
            blockers.append(
                "analysis_ready_dataset.record_count does not equal N*M"
            )

    expected_counts = run_plan.get("expected_execution_counts")
    if isinstance(expected_counts, dict) and case_count and model_count:
        if expected_counts.get("total_arm_outputs") != case_count * (
            1 + 3 * model_count
        ):
            blockers.append(
                "run plan total_arm_outputs is inconsistent with result design"
            )

    return ConfirmatoryResultReadiness(
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
