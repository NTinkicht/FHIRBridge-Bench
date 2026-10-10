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
_INPUT_TEMPLATE = Path(
    "analysis/examples/pilot_sample_size_inputs_template.yaml"
)


def _pilot_inputs() -> dict:
    return yaml.safe_load(_INPUT_TEMPLATE.read_text(encoding="utf-8"))


def test_assembler_rejects_comparison_set_drift() -> None:
    pilot = _pilot_inputs()
    pilot["paired_comparisons"][0]["comparison_id"] = "OTHER"

    with pytest.raises(ValueError, match="must match core design exactly"):
        _MODULE.assemble_sample_size_preregistration(
            pilot_inputs=pilot,
            pilot_case_manifest_sha256="1" * 64,
            pilot_analysis_sha256="2" * 64,
            record_id="SS-001",
            created_at="2026-10-20T10:00:00Z",
            core_design=_MODULE._load_yaml(_MODULE._CORE_DESIGN),
            method=_MODULE._load_yaml(_MODULE._METHOD),
            sample_size_method_sha256="3" * 64,
            core_confirmatory_design_sha256="4" * 64,
        )


def test_assembler_computes_ready_record_with_frozen_provenance() -> None:
    record = _MODULE.assemble_sample_size_preregistration(
        pilot_inputs=_pilot_inputs(),
        pilot_case_manifest_sha256="1" * 64,
        pilot_analysis_sha256="2" * 64,
        record_id="SS-001",
        created_at="2026-10-20T10:00:00Z",
        core_design=_MODULE._load_yaml(_MODULE._CORE_DESIGN),
        method=_MODULE._load_yaml(_MODULE._METHOD),
        sample_size_method_sha256="3" * 64,
        core_confirmatory_design_sha256="4" * 64,
    )

    assert record["schema_version"] == "0.4.0"
    assert record["status"] == "preregistered"
    assert record["frozen_method"]["sample_size_method_sha256"] == "3" * 64
    assert record["frozen_method"]["core_confirmatory_design_sha256"] == (
        "4" * 64
    )
    assert len(record["paired_comparison_plans"]) == 6
    assert {
        item["comparison_id"]
        for item in record["paired_comparison_plans"]
    } == {
        "BASELINE_vs_DIRECT",
        "BASELINE_vs_MAPPING",
        "BASELINE_vs_REPAIR",
        "DIRECT_vs_MAPPING",
        "DIRECT_vs_REPAIR",
        "MAPPING_vs_REPAIR",
    }
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


def test_cli_hashes_exact_pilot_files_and_writes_ready_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot_inputs = tmp_path / "pilot-inputs.yaml"
    pilot_inputs.write_text(
        _INPUT_TEMPLATE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    pilot_manifest = tmp_path / "pilot-case-manifest.yaml"
    pilot_manifest.write_text("pilot_cases: frozen\n", encoding="utf-8")
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
