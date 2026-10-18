import importlib.util
import json
from pathlib import Path

import pytest
import yaml

_MODULE_PATH = Path("analysis/build_analysis_dataset.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_analysis_dataset",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_SOURCE = "1" * 64


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _evidence() -> tuple[list[dict], list[dict]]:
    identities = [
        (None, "deterministic_baseline", "VALID", "FAITHFUL"),
        ("M1", "direct_structured_llm", "VALID", "UNFAITHFUL"),
        ("M1", "mapping_aware_llm", "VALID", "FAITHFUL"),
        (
            "M1",
            "mapping_aware_plus_syntax_repair",
            "POLICY_UNRESOLVED",
            "INDETERMINATE",
        ),
    ]
    structural: list[dict] = []
    semantic: list[dict] = []
    for index, (model_key, arm_id, outcome, verdict) in enumerate(
        identities,
        start=1,
    ):
        structural.append(
            {
                "schema_version": "0.1.0",
                "case_id": "C1",
                "model_key": model_key,
                "arm_id": arm_id,
                "source_input_sha256": _SOURCE,
                "structural_outcome": outcome,
                "validator_evidence_sha256": f"{index:x}" * 64,
            }
        )
        semantic.append(
            {
                "schema_version": "0.1.0",
                "case_id": "C1",
                "model_key": model_key,
                "arm_id": arm_id,
                "source_input_sha256": _SOURCE,
                "semantic_verdict": verdict,
                "verifier_evidence_sha256": f"{index + 4:x}" * 64,
                "evaluation_reason": (
                    "STRUCTURAL_NOT_VALID"
                    if outcome != "VALID"
                    else (
                        "VERIFIER_RUNTIME_INDETERMINATE"
                        if verdict == "INDETERMINATE"
                        else "PRIMARY_SEMANTIC_EVALUATION"
                    )
                ),
            }
        )
    return structural, semantic


def _fixture(tmp_path: Path) -> dict[str, Path]:
    manifest = tmp_path / "sealed-cases.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1.0",
                "manifest_id": "SEALED-CASES-001",
                "status": "sealed",
                "created_at": "2026-10-20T09:00:00Z",
                "split": "sealed_test",
                "case_count": 1,
                "cases": [
                    {
                        "case_id": "C1",
                        "scenario_family": "LAB-001",
                        "analysis_cluster_id": "SOURCE-C1",
                        "source_input_sha256": _SOURCE,
                        "canonical_graph_sha256": "2" * 64,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    run_plan = tmp_path / "run-plan.yaml"
    run_plan.write_text(
        yaml.safe_dump(
            {
                "sealed_set": {
                    "case_count": 1,
                    "case_manifest_sha256": _MODULE._sha256(manifest),
                },
                "model_keys": ["M1"],
                "expected_execution_counts": {"total_arm_outputs": 4},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    structural, semantic = _evidence()
    structural_path = tmp_path / "structural.jsonl"
    semantic_path = tmp_path / "semantic.jsonl"
    _write_jsonl(structural_path, structural)
    _write_jsonl(semantic_path, semantic)

    return {
        "manifest": manifest,
        "run_plan": run_plan,
        "structural": structural_path,
        "semantic": semantic_path,
    }


def test_analysis_dataset_builder_emits_exact_case_model_rows(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)

    rows, report = _MODULE.build_dataset(
        run_plan_path=paths["run_plan"],
        sealed_case_manifest_path=paths["manifest"],
        structural_evidence_path=paths["structural"],
        semantic_evidence_path=paths["semantic"],
    )

    assert len(rows) == 1
    assert rows[0]["case_id"] == "C1"
    assert rows[0]["model_key"] == "M1"
    assert report["analysis_row_count"] == 1
    assert report["structural_record_count"] == 4
    assert report["semantic_record_count"] == 4
    assert report["no_silent_exclusion_verified"] is True


def test_analysis_dataset_builder_rejects_manifest_changed_after_run_plan(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    manifest = yaml.safe_load(paths["manifest"].read_text(encoding="utf-8"))
    manifest["cases"][0]["canonical_graph_sha256"] = "f" * 64
    paths["manifest"].write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="do not match confirmatory run plan"):
        _MODULE.build_dataset(
            run_plan_path=paths["run_plan"],
            sealed_case_manifest_path=paths["manifest"],
            structural_evidence_path=paths["structural"],
            semantic_evidence_path=paths["semantic"],
        )


def test_analysis_dataset_builder_rejects_missing_arm_evidence(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    structural = [
        json.loads(line)
        for line in paths["structural"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    structural.pop()
    _write_jsonl(paths["structural"], structural)

    with pytest.raises(ValueError, match="arm outputs"):
        _MODULE.build_dataset(
            run_plan_path=paths["run_plan"],
            sealed_case_manifest_path=paths["manifest"],
            structural_evidence_path=paths["structural"],
            semantic_evidence_path=paths["semantic"],
        )


def test_analysis_dataset_builder_rejects_semantic_source_hash_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    semantic = [
        json.loads(line)
        for line in paths["semantic"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    semantic[0]["source_input_sha256"] = "f" * 64
    _write_jsonl(paths["semantic"], semantic)

    with pytest.raises(ValueError, match="does not match sealed case"):
        _MODULE.build_dataset(
            run_plan_path=paths["run_plan"],
            sealed_case_manifest_path=paths["manifest"],
            structural_evidence_path=paths["structural"],
            semantic_evidence_path=paths["semantic"],
        )
