import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path("models/build_baseline_qualification.py")
_SPEC = importlib.util.spec_from_file_location(
    "build_baseline_qualification",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def _record(template_id: str) -> dict:
    return {
        "schema_version": "0.1.0",
        "evidence_id": f"EVIDENCE-{template_id}",
        "template_id": template_id,
        "repository_commit": "abcdef1",
        "contract": {
            "id": "F2V-LAB-ORU-R01-001",
            "version": "0.3.0",
            "sha256": "1" * 64,
        },
        "target_profile": {
            "name": "LRI_NG_FRU_Profile_V3",
            "edition": "5",
            "errata": "2024DEC",
            "profile_bundle_sha256": "2" * 64,
            "qualification_report_sha256": "3" * 64,
        },
        "renderer_component": {
            "component_name": "deterministic_baseline_renderer",
            "artifact_id": "deterministic-fhir-to-hl7v2-baseline-renderer",
            "sha256": "4" * 64,
        },
        "order_context_present": True,
        "structural": {
            "outcome": "VALID",
            "validator_evidence_sha256": "5" * 64,
        },
        "semantic": {
            "verdict": "FAITHFUL",
            "verifier_evidence_sha256": "6" * 64,
        },
        "attestation": {
            "no_invented_business_facts": True,
            "development_placeholder_codes_absent": True,
            "confirmatory_model_outputs_not_used": True,
        },
    }


def _paths(tmp_path: Path) -> list[Path]:
    return [
        _write(tmp_path / f"LAB-{index:03d}.json", _record(f"LAB-{index:03d}"))
        for index in range(1, 12)
    ]


def test_baseline_aggregator_builds_exact_eleven_family_record(
    tmp_path: Path,
) -> None:
    result = _MODULE.build_baseline_qualification(
        _paths(tmp_path),
        qualification_id="BASELINE-QUAL-001",
        created_at="2026-10-20T22:00:00Z",
    )

    assert result["status"] == "qualified"
    assert result["aggregate"]["primary_family_count"] == 11
    assert [
        item["template_id"]
        for item in result["primary_family_evidence"]
    ] == [f"LAB-{index:03d}" for index in range(1, 12)]
    assert all(
        item["semantic_verdict"] == "FAITHFUL"
        for item in result["primary_family_evidence"]
    )


def test_baseline_aggregator_rejects_missing_family(tmp_path: Path) -> None:
    paths = _paths(tmp_path)[:-1]

    try:
        _MODULE.build_baseline_qualification(
            paths,
            qualification_id="BASELINE-QUAL-001",
            created_at="2026-10-20T22:00:00Z",
        )
    except ValueError as exc:
        assert "LAB-011" in str(exc)
    else:
        raise AssertionError("missing primary family must fail")


def test_baseline_aggregator_rejects_duplicate_family(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    duplicate = _write(tmp_path / "duplicate.json", _record("LAB-010"))
    paths.append(duplicate)

    try:
        _MODULE.build_baseline_qualification(
            paths,
            qualification_id="BASELINE-QUAL-001",
            created_at="2026-10-20T22:00:00Z",
        )
    except ValueError as exc:
        assert "duplicate baseline family evidence" in str(exc)
    else:
        raise AssertionError("duplicate primary family must fail")


def test_baseline_aggregator_rejects_cross_family_profile_drift(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    document = json.loads(paths[4].read_text(encoding="utf-8"))
    document["target_profile"]["profile_bundle_sha256"] = "f" * 64
    _write(paths[4], document)

    try:
        _MODULE.build_baseline_qualification(
            paths,
            qualification_id="BASELINE-QUAL-001",
            created_at="2026-10-20T22:00:00Z",
        )
    except ValueError as exc:
        assert "evidence drift detected" in str(exc)
        assert "LAB-005" in str(exc)
    else:
        raise AssertionError("profile drift must fail")


def test_baseline_aggregator_rejects_nonfaithful_family_at_schema_gate(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    document = json.loads(paths[6].read_text(encoding="utf-8"))
    document["semantic"]["verdict"] = "UNFAITHFUL"
    _write(paths[6], document)

    try:
        _MODULE.build_baseline_qualification(
            paths,
            qualification_id="BASELINE-QUAL-001",
            created_at="2026-10-20T22:00:00Z",
        )
    except Exception as exc:
        assert "FAITHFUL" in str(exc) or "const" in str(exc)
    else:
        raise AssertionError("unfaithful baseline family must fail")
