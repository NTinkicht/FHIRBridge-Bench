"""Build an immutable audit report from two independent contract reviews."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .contract_review import paired_review_summary, validate_complete_review_response


def _document_sha256(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_contract_review_pair_report(
    response_a: dict[str, Any],
    response_b: dict[str, Any],
    *,
    contract: dict[str, Any],
    relationship_candidates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate, compare, and summarize two original independent reviews.

    The input responses are treated as immutable evidence. The report records
    canonical hashes of both originals and never adjudicates or rewrites a
    reviewer decision.
    """

    validate_complete_review_response(
        response_a,
        contract,
        relationship_candidates=relationship_candidates,
    )
    validate_complete_review_response(
        response_b,
        contract,
        relationship_candidates=relationship_candidates,
    )
    summary = paired_review_summary(response_a, response_b)

    return {
        "report_id": "FHIRBRIDGE-CONTRACT-REVIEW-PAIR-001",
        "schema_version": "0.2.0",
        "contract": {
            "id": summary.contract_id,
            "version": summary.contract_version,
        },
        "reviewers": {
            "reviewer_a_id": summary.reviewer_a_id,
            "reviewer_b_id": summary.reviewer_b_id,
        },
        "source_review_sha256": {
            "reviewer_a": _document_sha256(response_a),
            "reviewer_b": _document_sha256(response_b),
        },
        "rule_count": len(summary.rule_ids),
        "rule_ids": list(summary.rule_ids),
        "agreement": {
            "n": summary.agreement.n,
            "labels": list(summary.agreement.labels),
            "raw_agreement": summary.agreement.raw_agreement,
            "cohens_kappa": summary.agreement.cohens_kappa,
            "gwets_ac1": summary.agreement.gwets_ac1,
            "confusion_matrix": summary.agreement.confusion_matrix,
        },
        "disagreement_count": len(summary.disagreements),
        "disagreements": [
            {
                "rule_id": item.rule_id,
                "reviewer_a_decision": item.reviewer_a_decision,
                "reviewer_b_decision": item.reviewer_b_decision,
            }
            for item in summary.disagreements
        ],
        "adjudication_required": bool(summary.disagreements),
        "review_stage": "blind",
        "agreement_input_policy": "original_blind_stage_labels_only",
        "original_reviews_preserved": True,
    }
