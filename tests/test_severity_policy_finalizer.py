import importlib.util
from copy import deepcopy
from pathlib import Path

import yaml

_MODULE_PATH = Path("expert_validation/finalize_severity_policy.py")
_SPEC = importlib.util.spec_from_file_location(
    "finalize_severity_policy",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_CANDIDATE = Path("benchmark/severity_policy_candidate.yaml")


def _reviewer(reviewer_id: str) -> dict:
    return {
        "reviewer_id": reviewer_id,
        "expertise": ["laboratory clinical informatics"],
        "conflicts_of_interest": "None declared",
        "prior_project_involvement": "None",
    }


def _anchor(
    anchor_id: str,
    role: str,
    left: str,
    right: str,
    adjudicated: str,
) -> dict:
    return {
        "anchor_id": anchor_id,
        "anchor_description": f"Calibration anchor {anchor_id}",
        "expected_boundary_role": role,
        "reviewer_ratings": [
            {
                "reviewer_id": "R-A",
                "severity": left,
                "rationale": "Independent rating A.",
            },
            {
                "reviewer_id": "R-B",
                "severity": right,
                "rationale": "Independent rating B.",
            },
        ],
        "adjudicated_severity": adjudicated,
        "adjudication_rationale": "Consensus after initial ratings.",
    }


def _calibration(candidate_hash: str) -> dict:
    return {
        "schema_version": "0.2.0",
        "calibration_id": "SEVERITY-CAL-001",
        "status": "completed",
        "created_at": "2026-10-20T18:00:00Z",
        "candidate_policy_sha256": candidate_hash,
        "blind_stage_evidence": {
            "assignment_id": "FHIRBRIDGE-SEVERITY-BLIND-001",
            "reviewer_a_response_sha256": "b" * 64,
            "reviewer_b_response_sha256": "c" * 64,
            "original_responses_retained": True,
            "boundary_roles_hidden_initially": True,
        },
        "reviewers": [_reviewer("R-A"), _reviewer("R-B")],
        "anchor_reviews": [
            _anchor("A1", "S1_S2_boundary", "S1", "S2", "S2"),
            _anchor("A2", "S2_S3_boundary", "S2", "S3", "S3"),
            _anchor("A3", "clear_S2_anchor", "S2", "S2", "S2"),
            _anchor("A4", "clear_S3_anchor", "S3", "S3", "S3"),
        ],
        "pre_adjudication_agreement": {
            "anchor_count": 4,
            "exact_agreement_count": 2,
            "exact_agreement_rate": 0.5,
            "disagreement_anchor_ids": ["A1", "A2"],
        },
        "major_threshold_decision": {
            "threshold": "S2_or_higher",
            "included_levels": ["S2", "S3"],
            "rationale": "Freeze clinically meaningful or worse as major.",
            "decision_status": "frozen_for_confirmatory_endpoint",
        },
        "attestation": {
            "independent_initial_ratings": True,
            "sealed_cases_used": False,
            "adjudication_after_initial_ratings": True,
            "all_disagreements_retained": True,
        },
    }


def _write_candidate(tmp_path: Path) -> Path:
    candidate = tmp_path / "severity-candidate.yaml"
    candidate.write_bytes(_CANDIDATE.read_bytes())
    return candidate


def _write_calibration(
    tmp_path: Path,
    candidate_path: Path,
    *,
    candidate_hash: str | None = None,
) -> Path:
    digest = candidate_hash or _MODULE._sha256(candidate_path)
    path = tmp_path / "severity-calibration.yaml"
    path.write_text(
        yaml.safe_dump(_calibration(digest), sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_finalizer_freezes_reviewed_candidate_without_changing_level_definitions(
    tmp_path: Path,
) -> None:
    candidate_path = _write_candidate(tmp_path)
    calibration_path = _write_calibration(tmp_path, candidate_path)
    original = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))

    frozen = _MODULE.finalize_severity_policy(
        candidate_path=candidate_path,
        calibration_path=calibration_path,
        calibration_ref="expert_validation/severity-calibration.yaml",
    )

    assert frozen["severity_policy"]["version"] == "1.0.0"
    assert frozen["severity_policy"]["status"] == "frozen"
    assert frozen["levels"] == original["levels"]
    assert frozen["primary_endpoint_major_candidate"]["levels"] == ["S2", "S3"]
    assert frozen["primary_endpoint_major_candidate"]["status"] == "frozen"
    assert frozen["primary_endpoint_major_candidate"]["threshold"] == (
        "S2_or_higher"
    )
    assert frozen["expert_calibration"]["status"] == "completed"
    assert frozen["expert_calibration"]["blind_assignment_id"] == (
        "FHIRBRIDGE-SEVERITY-BLIND-001"
    )
    assert frozen["expert_calibration"]["reviewer_a_response_sha256"] == "b" * 64
    assert frozen["expert_calibration"]["reviewer_b_response_sha256"] == "c" * 64
    assert frozen["expert_calibration"]["boundary_roles_hidden_initially"] is True
    assert frozen["expert_calibration"]["record_sha256"] == _MODULE._sha256(
        calibration_path
    )


def test_finalizer_rejects_calibration_of_different_candidate(
    tmp_path: Path,
) -> None:
    candidate_path = _write_candidate(tmp_path)
    calibration_path = _write_calibration(
        tmp_path,
        candidate_path,
        candidate_hash="f" * 64,
    )

    try:
        _MODULE.finalize_severity_policy(
            candidate_path=candidate_path,
            calibration_path=calibration_path,
            calibration_ref="expert_validation/severity-calibration.yaml",
        )
    except ValueError as exc:
        assert "not performed against this candidate policy" in str(exc)
    else:
        raise AssertionError("candidate hash mismatch must fail")


def test_finalizer_rejects_incomplete_calibration(tmp_path: Path) -> None:
    candidate_path = _write_candidate(tmp_path)
    calibration = _calibration(_MODULE._sha256(candidate_path))
    calibration["status"] = "incomplete_template"
    calibration_path = tmp_path / "incomplete.yaml"
    calibration_path.write_text(
        yaml.safe_dump(calibration, sort_keys=False),
        encoding="utf-8",
    )

    try:
        _MODULE.finalize_severity_policy(
            candidate_path=candidate_path,
            calibration_path=calibration_path,
            calibration_ref="expert_validation/severity-calibration.yaml",
        )
    except ValueError as exc:
        assert "not freeze-ready" in str(exc)
    else:
        raise AssertionError("incomplete calibration must fail")


def test_finalizer_applies_expert_selected_s3_only_threshold(
    tmp_path: Path,
) -> None:
    candidate_path = _write_candidate(tmp_path)
    calibration = deepcopy(_calibration(_MODULE._sha256(candidate_path)))
    calibration["major_threshold_decision"] = {
        "threshold": "S3_only",
        "included_levels": ["S3"],
        "rationale": "Calibration selected safety-critical errors only.",
        "decision_status": "frozen_for_confirmatory_endpoint",
    }
    calibration_path = tmp_path / "calibration-s3.yaml"
    calibration_path.write_text(
        yaml.safe_dump(calibration, sort_keys=False),
        encoding="utf-8",
    )

    frozen = _MODULE.finalize_severity_policy(
        candidate_path=candidate_path,
        calibration_path=calibration_path,
        calibration_ref="expert_validation/severity-calibration-s3.yaml",
    )

    assert frozen["primary_endpoint_major_candidate"]["levels"] == ["S3"]
    assert frozen["primary_endpoint_major_candidate"]["threshold"] == "S3_only"
