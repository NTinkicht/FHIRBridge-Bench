"""Build a reviewer-neutral machine-readable projectability review assignment."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .contract_review import expected_review_rule_ids


def _sha256(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_contract_review_assignment(
    contract: dict[str, Any],
    relationship_candidates: dict[str, Any],
    *,
    stage: str = "blind",
) -> dict[str, Any]:
    """Create an anti-anchoring two-stage external review assignment."""

    if stage not in {"blind", "unblinded"}:
        raise ValueError("stage must be 'blind' or 'unblinded'")

    header = contract.get("contract")
    if not isinstance(header, dict):
        raise ValueError("contract metadata is required")

    expected_ids = expected_review_rule_ids(
        contract,
        relationship_candidates=relationship_candidates,
    )

    contract_rules: dict[str, dict[str, Any]] = {}
    for rule in contract.get("rules", []):
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("rule_id")
        if isinstance(rule_id, str) and rule_id in expected_ids:
            contract_rules[rule_id] = {
                "rule_id": rule_id,
                "review_item_type": "contract_rule",
                "canonical_fact": rule.get("canonical_fact"),
                "source_paths": rule.get("source_paths", []),
                "target_paths": rule.get("target_paths", []),
                "proposed_projectability": rule.get("projectability"),
                "proposed_allowed_operations": rule.get("allowed_operations", []),
                "proposed_equivalence": rule.get("equivalence"),
                "proposed_failure_types": rule.get("failure_types", []),
                "proposed_severity": rule.get("severity_default"),
                "evidence": rule.get("evidence", []),
                "status": rule.get("status"),
            }

    candidate_rules: dict[str, dict[str, Any]] = {}
    for candidate in relationship_candidates.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        rule_id = candidate.get("candidate_rule_id")
        if isinstance(rule_id, str) and rule_id in expected_ids:
            candidate_rules[rule_id] = {
                "rule_id": rule_id,
                "review_item_type": "relationship_candidate",
                "canonical_relation": candidate.get("canonical_relation"),
                "source_semantics": candidate.get("source_semantics"),
                "target_semantics": candidate.get("target_semantics"),
                "proposed_projectability": candidate.get("current_projectability"),
                "proposed_allowed_operations": candidate.get(
                    "proposed_allowed_operations",
                    [],
                ),
                "proposed_failure_types": [
                    candidate.get("candidate_failure_class_if_scored")
                ],
                "proposed_severity": candidate.get("candidate_severity"),
                "evidence": candidate.get("evidence", []),
                "external_review_questions": candidate.get(
                    "external_review_questions",
                    [],
                ),
            }

    combined = {**contract_rules, **candidate_rules}
    missing = sorted(set(expected_ids) - set(combined))
    if missing:
        raise ValueError(
            "review assignment could not resolve expected rule IDs: "
            + ", ".join(missing)
        )

    assignment = {
        "assignment_id": "FHIRBRIDGE-CONTRACT-REVIEW-001",
        "schema_version": "0.1.0",
        "contract": {
            "id": header.get("id"),
            "version": header.get("version"),
        },
        "review_independence": {
            "model_outputs_permitted": False,
            "verifier_outputs_permitted": False,
            "renderer_outputs_permitted_as_correctness_evidence": False,
            "independent_initial_classification_required": True,
        },
        "review_item_count": len(expected_ids),
        "review_item_ids": list(expected_ids),
        "items": [combined[rule_id] for rule_id in expected_ids],
        "response_schema": (
            "contracts/review/contract_review_response.schema.json"
        ),
        "human_decisions_included": False,
    }
    assignment["review_stage"] = stage
    assignment["proposal_disclosure"] = (
        "withheld_for_independent_initial_classification"
        if stage == "blind"
        else "revealed_after_blind_response_lock"
    )
    assignment["review_independence"].update(
        {
            "blind_response_must_be_retained_before_unblinding": True,
            "reviewer_must_not_have_authored_project_rules": True,
            "reviewer_project_involvement_must_be_disclosed": True,
            "reviewer_lri_authoring_involvement_must_be_disclosed": True,
        }
    )
    if stage == "blind":
        proposal_keys = {
            "target_paths",
            "target_semantics",
            "proposed_projectability",
            "proposed_allowed_operations",
            "proposed_equivalence",
            "proposed_failure_types",
            "proposed_severity",
            "status",
        }
        for item in assignment["items"]:
            for key in proposal_keys:
                item.pop(key, None)

    assignment["assignment_sha256"] = _sha256(assignment)
    return assignment
