import importlib.util
from pathlib import Path

import yaml

_MODULE_PATH = Path("expert_validation/finalize_precedence_policy.py")
_SPEC = importlib.util.spec_from_file_location(
    "finalize_precedence_policy",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_CANDIDATE = Path("benchmark/error_precedence_policy_candidate.yaml")


def _review(candidate_hash: str, adjudicated: str = "ACCEPT") -> dict:
    return {
        "schema_version": "0.1.0",
        "review_id": "PRECEDENCE-REVIEW-001",
        "status": "completed",
        "created_at": "2026-10-20T19:00:00Z",
        "candidate_policy_sha256": candidate_hash,
        "reviewers": [
            {
                "reviewer_id": "R-A",
                "expertise": ["HL7 interoperability"],
                "conflicts_of_interest": "None declared",
                "prior_project_involvement": "None",
            },
            {
                "reviewer_id": "R-B",
                "expertise": ["clinical informatics"],
                "conflicts_of_interest": "None declared",
                "prior_project_involvement": "None",
            },
        ],
        "independent_decisions": [
            {
                "reviewer_id": "R-A",
                "decision": "ACCEPT",
                "rationale": "Candidate order is defensible.",
            },
            {
                "reviewer_id": "R-B",
                "decision": "ACCEPT",
                "rationale": "Candidate order is defensible.",
            },
        ],
        "adjudication": {
            "decision": adjudicated,
            "rationale": (
                "Consensus accepts the order."
                if adjudicated == "ACCEPT"
                else "Candidate requires revision."
            ),
        },
        "attestation": {
            "independent_initial_decisions": True,
            "other_reviewer_decisions_hidden_initially": True,
            "sealed_cases_used": False,
            "candidate_order_not_changed_during_adjudication": True,
        },
    }


def _write_candidate(tmp_path: Path) -> Path:
    path = tmp_path / "precedence-candidate.yaml"
    path.write_bytes(_CANDIDATE.read_bytes())
    return path


def _write_review(
    tmp_path: Path,
    candidate_path: Path,
    *,
    candidate_hash: str | None = None,
    adjudicated: str = "ACCEPT",
) -> Path:
    digest = candidate_hash or _MODULE._sha256(candidate_path)
    path = tmp_path / "precedence-review.yaml"
    path.write_text(
        yaml.safe_dump(_review(digest, adjudicated), sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_finalizer_freezes_exact_accepted_candidate(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path)
    review = _write_review(tmp_path, candidate)
    original = yaml.safe_load(candidate.read_text(encoding="utf-8"))

    frozen = _MODULE.finalize_precedence_policy(
        candidate_path=candidate,
        review_path=review,
        review_ref="expert_validation/precedence-review.yaml",
    )

    assert frozen["precedence_policy"]["version"] == "1.0.0"
    assert frozen["precedence_policy"]["status"] == "frozen"
    assert frozen["order"] == original["order"]
    assert frozen["rule"] == original["rule"]
    assert frozen["expert_review"]["status"] == "completed"
    assert frozen["expert_review"]["adjudicated_decision"] == "ACCEPT"
    assert frozen["expert_review"]["review_sha256"] == _MODULE._sha256(review)


def test_finalizer_rejects_review_of_different_candidate(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path)
    review = _write_review(
        tmp_path,
        candidate,
        candidate_hash="f" * 64,
    )

    try:
        _MODULE.finalize_precedence_policy(
            candidate_path=candidate,
            review_path=review,
            review_ref="expert_validation/precedence-review.yaml",
        )
    except ValueError as exc:
        assert "not performed against this candidate policy" in str(exc)
    else:
        raise AssertionError("candidate hash mismatch must fail")


def test_finalizer_rejects_adjudicated_rejection(tmp_path: Path) -> None:
    candidate = _write_candidate(tmp_path)
    review = _write_review(
        tmp_path,
        candidate,
        adjudicated="REJECT",
    )

    try:
        _MODULE.finalize_precedence_policy(
            candidate_path=candidate,
            review_path=review,
            review_ref="expert_validation/precedence-review.yaml",
        )
    except ValueError as exc:
        assert "did not accept the candidate policy" in str(exc)
    else:
        raise AssertionError("rejected precedence candidate must not freeze")
