import importlib.util
import sys
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path("analysis/build_primary_vur_hypothesis.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_primary_vur_hypothesis_cli",
    _SCRIPT,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_cli_hashes_pilot_inputs_and_writes_ready_hypothesis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot_manifest = tmp_path / "pilot-manifest.yaml"
    pilot_manifest.write_text("pilot: frozen\n", encoding="utf-8")
    pilot_analysis = tmp_path / "pilot-analysis.yaml"
    pilot_analysis.write_text("vur: 0.17\n", encoding="utf-8")
    output = tmp_path / "primary-hypothesis.yaml"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(_SCRIPT),
            "--pilot-case-manifest",
            str(pilot_manifest),
            "--pilot-analysis",
            str(pilot_analysis),
            "--record-id",
            "PRIMARY-VUR-001",
            "--created-at",
            "2026-10-20T16:00:00Z",
            "--threshold",
            "0.10",
            "--threshold-rationale",
            "Pilot-derived non-trivial semantic-error threshold.",
            "--inclusion-rule",
            "Frozen eligible FHIR-to-HL7v2 LLM transformations.",
            "--aggregation-policy",
            "Frozen cluster-aware aggregation across model/strategy rows.",
            "--inference-method",
            "cluster_aware_one_sided_threshold_test",
            "--cluster-handling",
            "Use frozen analysis_cluster_id without post-run regrouping.",
            "--confidence-interval-method",
            "Frozen cluster-aware one-sided 95% interval.",
            "--decision-rule",
            "Reject H0 only under the frozen method at alpha 0.05.",
            "--output",
            str(output),
        ],
    )

    assert _MODULE.main() == 0
    record = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert record["status"] == "preregistered"
    assert record["hypothesis"]["nontrivial_vur_threshold"] == 0.10
    assert record["pilot_evidence"]["pilot_case_manifest_sha256"] == sha256(
        pilot_manifest.read_bytes()
    ).hexdigest()
    assert record["pilot_evidence"]["pilot_analysis_sha256"] == sha256(
        pilot_analysis.read_bytes()
    ).hexdigest()
    assert record["target_population"]["cluster_id_field"] == (
        "analysis_cluster_id"
    )


def test_cli_rejects_placeholder_inference_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot_manifest = tmp_path / "pilot-manifest.yaml"
    pilot_manifest.write_text("pilot: frozen\n", encoding="utf-8")
    pilot_analysis = tmp_path / "pilot-analysis.yaml"
    pilot_analysis.write_text("vur: 0.17\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(_SCRIPT),
            "--pilot-case-manifest",
            str(pilot_manifest),
            "--pilot-analysis",
            str(pilot_analysis),
            "--record-id",
            "PRIMARY-VUR-001",
            "--created-at",
            "2026-10-20T16:00:00Z",
            "--threshold",
            "0.10",
            "--threshold-rationale",
            "Pilot-derived threshold.",
            "--inclusion-rule",
            "Frozen eligible population.",
            "--aggregation-policy",
            "Frozen aggregation.",
            "--inference-method",
            "TO_BE_FROZEN",
            "--cluster-handling",
            "Frozen analysis_cluster_id.",
            "--confidence-interval-method",
            "Frozen interval.",
            "--decision-rule",
            "Frozen rule.",
        ],
    )

    with pytest.raises(ValueError, match="not ready"):
        _MODULE.main()
