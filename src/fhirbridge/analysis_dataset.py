"""Build no-silent-exclusion confirmatory analysis rows."""

from __future__ import annotations

from typing import Any

from .sealed_case_manifest import source_input_sha256_by_case

_BASELINE = "deterministic_baseline"
_LLM_ARMS = (
    "direct_structured_llm",
    "mapping_aware_llm",
    "mapping_aware_plus_syntax_repair",
)
_ALL_ARMS = (_BASELINE, *_LLM_ARMS)
_STRUCTURAL = frozenset(
    {"VALID", "INVALID", "MEASUREMENT_FAILURE", "POLICY_UNRESOLVED"}
)
_SEMANTIC = frozenset({"FAITHFUL", "UNFAITHFUL", "INDETERMINATE"})


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
        and set(value.lower()) != {"0"}
    )


def _identity(record: dict[str, Any]) -> tuple[str, str | None, str]:
    case_id = record.get("case_id")
    model_key = record.get("model_key")
    arm_id = record.get("arm_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("evidence record lacks case_id")
    if arm_id not in _ALL_ARMS:
        raise ValueError(f"unsupported evidence arm_id: {arm_id!r}")
    if arm_id == _BASELINE:
        if model_key is not None:
            raise ValueError("baseline evidence model_key must be null")
    elif not isinstance(model_key, str) or not model_key:
        raise ValueError("LLM evidence record requires model_key")
    return case_id, model_key, str(arm_id)


def _index(
    records: list[dict[str, Any]],
    *,
    kind: str,
) -> dict[tuple[str, str | None, str], dict[str, Any]]:
    result: dict[tuple[str, str | None, str], dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{kind} evidence contains malformed record")
        key = _identity(record)
        if key in result:
            raise ValueError(
                f"duplicate {kind} evidence record: "
                + "/".join("" if value is None else value for value in key)
            )
        result[key] = record
    return result


def _expected_keys(
    case_ids: set[str],
    model_keys: list[str],
) -> set[tuple[str, str | None, str]]:
    keys: set[tuple[str, str | None, str]] = {
        (case_id, None, _BASELINE) for case_id in case_ids
    }
    keys.update(
        (case_id, model_key, arm_id)
        for case_id in case_ids
        for model_key in model_keys
        for arm_id in _LLM_ARMS
    )
    return keys


def _check_exact_coverage(
    observed: set[tuple[str, str | None, str]],
    expected: set[tuple[str, str | None, str]],
    *,
    kind: str,
) -> None:
    missing = expected - observed
    unexpected = observed - expected
    if missing or unexpected:
        def render(
            keys: set[tuple[str, str | None, str]],
        ) -> list[str]:
            return [
                "/".join("" if value is None else value for value in key)
                for key in sorted(
                    keys,
                    key=lambda item: (
                        item[0],
                        "" if item[1] is None else item[1],
                        item[2],
                    ),
                )
            ]

        raise ValueError(
            f"{kind} evidence does not match planned arm set; "
            f"missing={render(missing)}, unexpected={render(unexpected)}"
        )


def _arm_state(
    structural: dict[str, Any],
    semantic: dict[str, Any],
    *,
    expected_source_hash: str,
) -> dict[str, Any]:
    structural_source = structural.get("source_input_sha256")
    semantic_source = semantic.get("source_input_sha256")
    if not _valid_sha256(structural_source) or not _valid_sha256(
        semantic_source
    ):
        raise ValueError("evidence source_input_sha256 is missing or invalid")
    if str(structural_source).lower() != expected_source_hash.lower():
        raise ValueError(
            "structural evidence source_input_sha256 does not match sealed case"
        )
    if str(semantic_source).lower() != expected_source_hash.lower():
        raise ValueError(
            "semantic evidence source_input_sha256 does not match sealed case"
        )

    structural_outcome = structural.get("structural_outcome")
    semantic_verdict = semantic.get("semantic_verdict")
    reason = semantic.get("evaluation_reason")
    if structural_outcome not in _STRUCTURAL:
        raise ValueError(
            f"unsupported structural outcome: {structural_outcome!r}"
        )
    if semantic_verdict not in _SEMANTIC:
        raise ValueError(
            f"unsupported semantic verdict: {semantic_verdict!r}"
        )

    if structural_outcome != "VALID":
        if (
            semantic_verdict != "INDETERMINATE"
            or reason != "STRUCTURAL_NOT_VALID"
        ):
            raise ValueError(
                "non-VALID structural output must remain semantic "
                "INDETERMINATE with STRUCTURAL_NOT_VALID reason"
            )
    elif semantic_verdict == "INDETERMINATE":
        if reason != "VERIFIER_RUNTIME_INDETERMINATE":
            raise ValueError(
                "VALID semantic INDETERMINATE requires runtime-indeterminate reason"
            )
    elif reason != "PRIMARY_SEMANTIC_EVALUATION":
        raise ValueError(
            "determinate semantic verdict requires primary-evaluation reason"
        )

    structural_evidence = structural.get("validator_evidence_sha256")
    semantic_evidence = semantic.get("verifier_evidence_sha256")
    if not _valid_sha256(structural_evidence):
        raise ValueError("validator_evidence_sha256 is missing or invalid")
    if not _valid_sha256(semantic_evidence):
        raise ValueError("verifier_evidence_sha256 is missing or invalid")

    return {
        "structural_outcome": structural_outcome,
        "semantic_verdict": semantic_verdict,
        "semantic_evaluation_reason": reason,
        "vur_eligible": (
            structural_outcome == "VALID"
            and semantic_verdict != "INDETERMINATE"
        ),
        "vfy_success": (
            structural_outcome == "VALID"
            and semantic_verdict == "FAITHFUL"
        ),
        "structural_evidence_sha256": str(structural_evidence).lower(),
        "semantic_evidence_sha256": str(semantic_evidence).lower(),
    }


def build_analysis_rows(
    *,
    sealed_case_manifest: dict[str, Any],
    model_keys: list[str],
    structural_records: list[dict[str, Any]],
    semantic_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join complete arm evidence into one row per sealed case and model."""

    if not model_keys or any(
        not isinstance(model, str) or not model for model in model_keys
    ):
        raise ValueError("model_keys must contain non-empty strings")
    if len(model_keys) != len(set(model_keys)):
        raise ValueError("model_keys must be unique")

    source_hashes = source_input_sha256_by_case(sealed_case_manifest)
    case_ids = set(source_hashes)
    expected = _expected_keys(case_ids, model_keys)
    structural_by_key = _index(structural_records, kind="structural")
    semantic_by_key = _index(semantic_records, kind="semantic")
    _check_exact_coverage(
        set(structural_by_key),
        expected,
        kind="structural",
    )
    _check_exact_coverage(
        set(semantic_by_key),
        expected,
        kind="semantic",
    )

    baseline_states: dict[str, dict[str, Any]] = {}
    for case_id in sorted(case_ids):
        key = (case_id, None, _BASELINE)
        baseline_states[case_id] = _arm_state(
            structural_by_key[key],
            semantic_by_key[key],
            expected_source_hash=source_hashes[case_id],
        )

    rows: list[dict[str, Any]] = []
    for case_id in sorted(case_ids):
        for model_key in sorted(model_keys):
            arms: dict[str, dict[str, Any]] = {
                _BASELINE: dict(baseline_states[case_id])
            }
            for arm_id in _LLM_ARMS:
                key = (case_id, model_key, arm_id)
                arms[arm_id] = _arm_state(
                    structural_by_key[key],
                    semantic_by_key[key],
                    expected_source_hash=source_hashes[case_id],
                )
            rows.append(
                {
                    "schema_version": "0.1.0",
                    "case_id": case_id,
                    "model_key": model_key,
                    "source_input_sha256": source_hashes[case_id],
                    "arms": arms,
                }
            )
    return rows
