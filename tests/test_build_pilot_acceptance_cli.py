import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path("expert_validation/build_pilot_acceptance.py")
_SPEC = importlib.util.spec_from_file_location("build_pilot_acceptance_cli", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_sha256_arg_rejects_non_digest() -> None:
    with pytest.raises(ValueError, match="64-character SHA-256"):
        _MODULE._sha256_arg("not-a-digest", "verifier-sha256")


def test_load_list_accepts_json_and_rejects_mapping(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text(json.dumps([{"case_id": "C1"}]), encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text("case_id: C1\n", encoding="utf-8")

    assert _MODULE._load_list(good, "items") == [{"case_id": "C1"}]
    with pytest.raises(ValueError, match="non-empty JSON/YAML list"):
        _MODULE._load_list(bad, "items")


def test_cli_builds_ready_record_and_hashes_case_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adjudications = tmp_path / "adjudications.json"
    adjudications.write_text(
        json.dumps(
            [
                {"case_id": "C1", "adjudicated_verdict": "YES"},
                {"case_id": "C2", "adjudicated_verdict": "YES"},
                {"case_id": "C3", "adjudicated_verdict": "NO"},
                {"case_id": "C4", "adjudicated_verdict": "NO"},
            ]
        ),
        encoding="utf-8",
    )
    verifier = tmp_path / "verifier.json"
    verifier.write_text(
        json.dumps(
            [
                {"case_id": "C1", "semantic_verdict": "UNFAITHFUL"},
                {"case_id": "C2", "semantic_verdict": "INDETERMINATE"},
                {"case_id": "C3", "semantic_verdict": "FAITHFUL"},
                {"case_id": "C4", "semantic_verdict": "FAITHFUL"},
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "pilot-manifest.yaml"
    manifest.write_text("pilot: frozen\n", encoding="utf-8")
    output = tmp_path / "pilot-record.yaml"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(_SCRIPT),
            "--adjudications",
            str(adjudications),
            "--verifier-results",
            str(verifier),
            "--pilot-case-manifest",
            str(manifest),
            "--record-id",
            "PILOT-001",
            "--created-at",
            "2026-10-20T10:00:00Z",
            "--repository-commit",
            "abcdef1",
            "--verifier-sha256",
            "1" * 64,
            "--projectability-contract-sha256",
            "2" * 64,
            "--minimum-sensitivity",
            "0.4",
            "--sensitivity-statistic",
            "point_estimate",
            "--sensitivity-rationale",
            "Pilot-derived sensitivity floor.",
            "--minimum-ppv",
            "0.8",
            "--ppv-statistic",
            "point_estimate",
            "--ppv-rationale",
            "Pilot-derived PPV floor.",
            "--maximum-runtime-indeterminate-rate",
            "0.3",
            "--indeterminate-statistic",
            "point_estimate",
            "--indeterminate-rationale",
            "Pilot-derived abstention ceiling.",
            "--output",
            str(output),
        ],
    )

    assert _MODULE.main() == 0
    record = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert record["schema_version"] == "0.5.0"
    assert record["status"] == "preregistered"
    assert record["pilot_evidence"]["pilot_case_manifest_sha256"] == sha256(
        manifest.read_bytes()
    ).hexdigest()
    assert len(
        record["pilot_evidence"]["pilot_verifier_results_bundle_sha256"]
    ) == 64
    assert record["metrics"]["runtime_indeterminate_count"] == 1
    assert record["acceptance_gate"]["maximum_runtime_indeterminate_rate"] == 0.3
