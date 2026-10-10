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


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
        and not _zeroish(value)
    )


def _valid_commit(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 7 <= len(value) <= 40
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
        and not _zeroish(value)
    )


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
    if not _valid_sha256(digest):
        blockers.append(f"{label}.sha256 is missing, malformed, or placeholder")


def assess_confirmatory_result_manifest(
    document: dict[str, Any],
    *,
    run_plan: dict[str, Any],
    run_plan_sha256: str,
) -> ConfirmatoryResultReadiness:
    """Validate immutable execution-to-analysis provenance against the run plan."""

    blockers: list[str] = []

    if document.get("schema_version") != "0.3.0":
        blockers.append("result manifest schema_version is not 0.3.0")
    if document.get("status") != "execution_complete_audited":
        blockers.append("result manifest is not execution_complete_audited")
    if document.get("created_at") is None:
        blockers.append("result manifest has no creation timestamp")
    if _placeholder(document.get("result_manifest_id")):
        blockers.append("result_manifest_id is still a placeholder")
    result_commit = document.get("repository_commit")
    if not _valid_commit(result_commit):
        blockers.append("repository_commit is missing, malformed, or placeholder")
    run_commit = run_plan.get("repository_commit")
    if not _valid_commit(run_commit):
        blockers.append("run plan repository_commit is missing or malformed")
    elif (
        isinstance(result_commit, str)
        and _valid_commit(result_commit)
        and result_commit.lower() != str(run_commit).lower()
    ):
        blockers.append("result repository_commit does not match run plan")

    if not _valid_sha256(run_plan_sha256):
        blockers.append("supplied run_plan_sha256 is missing or malformed")
    if not _valid_sha256(document.get("run_plan_sha256")):
        blockers.append("result manifest run_plan_sha256 is missing or malformed")
    elif document.get("run_plan_sha256") != run_plan_sha256:
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
    if (
        not isinstance(case_count, int)
        or isinstance(case_count, bool)
        or case_count < 1
    ):
        blockers.append("run plan case_count is invalid")
        case_count = 0

    raw = document.get("raw_execution_records")
    baseline = document.get("deterministic_baseline_outputs")
    schema_validation = document.get("execution_schema_validation")
    audit = document.get("execution_audit")
    structural = document.get("structural_validation_evidence")
    semantic = document.get("semantic_verification_evidence")
    analysis_build = document.get("analysis_dataset_build")
    analysis = document.get("analysis_ready_dataset")
    _artifact_blockers(raw, label="raw_execution_records", blockers=blockers)
    _artifact_blockers(
        baseline,
        label="deterministic_baseline_outputs",
        blockers=blockers,
    )
    _artifact_blockers(
        schema_validation,
        label="execution_schema_validation",
        blockers=blockers,
    )
    _artifact_blockers(audit, label="execution_audit", blockers=blockers)
    _artifact_blockers(
        structural,
        label="structural_validation_evidence",
        blockers=blockers,
    )
    _artifact_blockers(
        semantic,
        label="semantic_verification_evidence",
        blockers=blockers,
    )
    _artifact_blockers(
        analysis_build,
        label="analysis_dataset_build",
        blockers=blockers,
    )
    _artifact_blockers(
        analysis,
        label="analysis_ready_dataset",
        blockers=blockers,
    )

    if (
        isinstance(schema_validation, dict)
        and schema_validation.get("complete") is not True
    ):
        blockers.append("execution schema validation is not complete")
    if isinstance(audit, dict) and audit.get("complete") is not True:
        blockers.append("execution audit is not complete")

    if (
        isinstance(analysis_build, dict)
        and analysis_build.get("complete") is not True
    ):
        blockers.append("analysis dataset build audit is not complete")

    if case_count and model_count:
        expected_raw = case_count * model_count * 3
        expected_baseline = case_count
        expected_analysis_rows = case_count * model_count
        expected_arm_outputs = case_count * (1 + 3 * model_count)
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
        if (
            isinstance(structural, dict)
            and structural.get("record_count") != expected_arm_outputs
        ):
            blockers.append(
                "structural_validation_evidence.record_count does not equal "
                "total arm outputs"
            )
        if (
            isinstance(semantic, dict)
            and semantic.get("record_count") != expected_arm_outputs
        ):
            blockers.append(
                "semantic_verification_evidence.record_count does not equal "
                "total arm outputs"
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
