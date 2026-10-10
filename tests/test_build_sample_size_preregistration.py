import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path

import jsonschema
import pytest
import yaml

_SCRIPT = Path("analysis/build_sample_size_preregistration.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_sample_size_preregistration_cli",
    _SCRIPT,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_OUTPUT_SCHEMA = Path(
    "analysis/schema/sample_size_preregistration.schema.json"
)
_BASE = (
    "BASELINE_vs_DIRECT",
    "BASELINE_vs_MAPPING",
    "BASELINE_vs_REPAIR",
    "DIRECT_vs_MAPPING",
    "DIRECT_vs_REPAIR",
    "MAPPING_vs_REPAIR",
)


def _pilot_inputs(model_keys: tuple[str, ...] = ("MODEL-A",)) -> dict:
    rows = []
    for model_key in model_keys:
        for base_id in _BASE:
            rows.append(
                {
                    "model_key": model_key,
                    "comparison_id": f"{model_key}__{base_id}",
                    "p10": 0.10,
                    "p01": 0.05,
                    "expected_pair_retention": 1.0,
                }
            )
    return {
        "schema_version": "0.2.0",
        "expected_vur": 0.20,
        "valid_determinate_retention": 0.80,
        "mean_cluster_size": 2.0,
        "icc": 0.10,
        "target_half_width": 0.05,
        "model_keys": list(model_keys),
        "paired_comparisons": rows,
    }


def _model_config(model_keys: tuple[str, ...] = ("MODEL-A",)) -> dict:
    return {
        "llm_models": [
            {"model_key": model_key}
            for model_key in model_keys
        ]
    }


def _assemble(
    model_keys: tuple[str, ...] = ("MODEL-A",),
    *,
    pilot_inputs: dict | None = None,
) -> dict:
    return _MODULE.assemble_sample_size_preregistration(
        pilot_inputs=pilot_inputs or _pilot_inputs(model_keys),
        pilot_case_manifest_sha256="1" * 64,
        pilot_analysis_sha256="2" * 64,
        record_id="SS-001",
        created_at="2026-10-20T10:00:00Z",
        core_design=_MODULE._load_yaml(_MODULE._CORE_DESIGN),
        method=_MODULE._load_yaml(_MODULE._METHOD),
        model_config=_model_config(model_keys),
        sample_size_method_sha256="3" * 64,
        core_confirmatory_design_sha256="4" * 64,
        model_prompt_configuration_sha256="5" * 64,
    )


def test_assembler_rejects_comparison_set_drift() -> None:
    pilot = _pilot_inputs()
    pilot["paired_comparisons"][0]["comparison_id"] = "MODEL-A__OTHER"

    with pytest.raises(
        ValueError,
        match="model-specific core design exactly",
    ):
        _assemble(pilot_inputs=pilot)


def test_assembler_rejects_model_key_drift_from_frozen_config() -> None:
    pilot = _pilot_inputs(("MODEL-A",))
    pilot["model_keys"] = ["MODEL-B"]

    with pytest.raises(
        ValueError,
        match="must exactly match frozen model configuration",
    ):
        _assemble(pilot_inputs=pilot)


def test_assembler_computes_ready_record_with_frozen_provenance() -> None:
    record = _assemble()

    assert record["schema_version"] == "0.5.0"
    assert record["status"] == "preregistered"
    assert record["model_keys"] == ["MODEL-A"]
    assert record["frozen_method"]["sample_size_method_sha256"] == "3" * 64
    assert record["frozen_method"]["core_confirmatory_design_sha256"] == (
        "4" * 64
    )
    assert record["frozen_method"]["model_prompt_configuration_sha256"] == (
        "5" * 64
    )
    assert len(record["paired_comparison_plans"]) == 6
    assert {
        item["comparison_id"]
        for item in record["paired_comparison_plans"]
    } == {f"MODEL-A__{base_id}" for base_id in _BASE}
    assert record["multiplicity"]["comparison_family_size"] == 6
    assert record["multiplicity"]["per_comparison_planning_alpha"] == (
        pytest.approx(0.05 / 6)
    )
    expected_final = max(
        record["primary_precision_plan"]["planned_source_cluster_count"],
        *[
            item["planned_source_cluster_count"]
            for item in record["paired_comparison_plans"]
        ],
    )
    assert record["final_source_cluster_count"] == expected_final

    schema = json.loads(_OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(record)


def test_two_models_expand_to_twelve_plans_and_alpha_over_full_family() -> None:
    record = _assemble(("MODEL-A", "MODEL-B"))

    assert record["model_keys"] == ["MODEL-A", "MODEL-B"]
    assert len(record["paired_comparison_plans"]) == 12
    assert record["multiplicity"]["comparison_family_size"] == 12
    assert record["multiplicity"]["per_comparison_planning_alpha"] == (
        pytest.approx(0.05 / 12)
    )
    assert {
        item["model_key"]
        for item in record["paired_comparison_plans"]
    } == {"MODEL-A", "MODEL-B"}


def test_cli_hashes_pilot_and_model_files_and_writes_ready_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot_inputs = tmp_path / "pilot-inputs.yaml"
    pilot_inputs.write_text(
        yaml.safe_dump(_pilot_inputs(), sort_keys=False),
        encoding="utf-8",
    )
    pilot_manifest = tmp_path / "pilot-case-manifest.yaml"
    pilot_manifest.write_text("pilot_cases: frozen\n", encoding="utf-8")
    model_config = tmp_path / "model-config.yaml"
    model_config.write_text(
        yaml.safe_dump(_model_config(), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "sample-size.yaml"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(_SCRIPT),
            "--pilot-inputs",
            str(pilot_inputs),
            "--pilot-case-manifest",
            str(pilot_manifest),
            "--model-config",
            str(model_config),
            "--record-id",
            "SS-CLI-001",
            "--created-at",
            "2026-10-20T11:00:00Z",
            "--output",
            str(output),
        ],
    )

    assert _MODULE.main() == 0
    record = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert record["pilot_evidence"]["pilot_case_manifest_sha256"] == sha256(
        pilot_manifest.read_bytes()
    ).hexdigest()
    assert record["pilot_evidence"]["pilot_analysis_sha256"] == sha256(
        pilot_inputs.read_bytes()
    ).hexdigest()
    assert record["frozen_method"]["sample_size_method_sha256"] == sha256(
        _MODULE._METHOD.read_bytes()
    ).hexdigest()
    assert record["frozen_method"]["core_confirmatory_design_sha256"] == sha256(
        _MODULE._CORE_DESIGN.read_bytes()
    ).hexdigest()
    assert record["frozen_method"]["model_prompt_configuration_sha256"] == sha256(
        model_config.read_bytes()
    ).hexdigest()
