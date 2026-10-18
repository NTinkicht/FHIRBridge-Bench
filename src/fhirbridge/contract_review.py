"""Utilities for preserving and comparing independent contract reviews.

The comparison layer treats original reviewer decisions as immutable inputs. It
computes agreement and surfaces disagreements but does not adjudicate or rewrite
reviewer labels.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .agreement import AgreementResult, agreement_statistics


@dataclass(frozen=True)
class RuleDisagreement:
    rule_id: str
    reviewer_a_decision: str
    reviewer_b_decision: str


@dataclass(frozen=True)
class PairedReviewSummary:
    contract_id: str
    contract_version: str
    reviewer_a_id: str
    reviewer_b_id: str
    rule_ids: tuple[str, ...]
    agreement: AgreementResult
    disagreements: tuple[RuleDisagreement, ...]


def _reviewer_id(response: dict[str, Any]) -> str:
    reviewer = response.get("reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("review response must contain a reviewer mapping")
    reviewer_id = reviewer.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        raise ValueError("reviewer.reviewer_id must be a non-empty string")
    return reviewer_id


def _contract_key(response: dict[str, Any]) -> tuple[str, str]:
    contract = response.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("review response must contain a contract mapping")
    contract_id = contract.get("id")
    version = contract.get("version")
    if not isinstance(contract_id, str) or not contract_id:
        raise ValueError("contract.id must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("contract.version must be a non-empty string")
    return contract_id, version


def review_rule_ids(response: dict[str, Any]) -> tuple[str, ...]:
    """Return unique reviewed rule IDs without assuming a review stage."""

    reviews = response.get("rule_reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("rule_reviews must be a non-empty list")
    observed: set[str] = set()
    for item in reviews:
        if not isinstance(item, dict):
            raise ValueError("each rule review must be a mapping")
        rule_id = item.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("each rule review needs a non-empty rule_id")
        if rule_id in observed:
            raise ValueError(f"duplicate rule review: {rule_id}")
        observed.add(rule_id)
    return tuple(sorted(observed))


def decisions_by_rule(response: dict[str, Any]) -> dict[str, str]:
    """Return original projectability decisions indexed by rule ID."""

    reviews = response.get("rule_reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("rule_reviews must be a non-empty list")

    decisions: dict[str, str] = {}
    for item in reviews:
        if not isinstance(item, dict):
            raise ValueError("each rule review must be a mapping")
        rule_id = item.get("rule_id")
        decision = item.get("projectability_decision")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("each rule review needs a non-empty rule_id")
        if not isinstance(decision, str) or not decision:
            raise ValueError(
                f"rule {rule_id} needs a non-empty projectability_decision"
            )
        if rule_id in decisions:
            raise ValueError(f"duplicate rule review: {rule_id}")
        decisions[rule_id] = decision
    return decisions


def paired_review_summary(
    response_a: dict[str, Any],
    response_b: dict[str, Any],
) -> PairedReviewSummary:
    """Compare two independent reviews of the same contract rule set."""

    stage_a = response_a.get("review_stage", "legacy")
    stage_b = response_b.get("review_stage", "legacy")
    if stage_a not in {"blind", "legacy"} or stage_b not in {"blind", "legacy"}:
        raise ValueError(
            "inter-rater agreement must use original blind-stage responses"
        )

    contract_a = _contract_key(response_a)
    contract_b = _contract_key(response_b)
    if contract_a != contract_b:
        raise ValueError(
            "review responses must reference the same contract ID and version"
        )

    reviewer_a = _reviewer_id(response_a)
    reviewer_b = _reviewer_id(response_b)
    if reviewer_a == reviewer_b:
        raise ValueError("paired agreement requires two distinct reviewer IDs")

    decisions_a = decisions_by_rule(response_a)
    decisions_b = decisions_by_rule(response_b)
    rules_a = set(decisions_a)
    rules_b = set(decisions_b)
    if rules_a != rules_b:
        missing_from_a = sorted(rules_b - rules_a)
        missing_from_b = sorted(rules_a - rules_b)
        raise ValueError(
            "review responses must cover the same rule set; "
            f"missing from A={missing_from_a}, missing from B={missing_from_b}"
        )

    rule_ids = tuple(sorted(rules_a))
    labels_a = [decisions_a[rule_id] for rule_id in rule_ids]
    labels_b = [decisions_b[rule_id] for rule_id in rule_ids]
    agreement = agreement_statistics(labels_a, labels_b)
    disagreements = tuple(
        RuleDisagreement(
            rule_id=rule_id,
            reviewer_a_decision=decisions_a[rule_id],
            reviewer_b_decision=decisions_b[rule_id],
        )
        for rule_id in rule_ids
        if decisions_a[rule_id] != decisions_b[rule_id]
    )

    return PairedReviewSummary(
        contract_id=contract_a[0],
        contract_version=contract_a[1],
        reviewer_a_id=reviewer_a,
        reviewer_b_id=reviewer_b,
        rule_ids=rule_ids,
        agreement=agreement,
        disagreements=disagreements,
    )


def expected_review_rule_ids(
    contract: dict[str, Any],
    *,
    relationship_candidates: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    """Return the complete rule set that independent reviewers must address."""

    rules = contract.get("rules")
    if not isinstance(rules, list):
        raise ValueError("contract.rules must be a list")

    expected: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("every contract rule must be a mapping")
        if rule.get("expert_review_required") is not True:
            continue
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("expert-reviewed contract rule requires rule_id")
        if rule_id in expected:
            raise ValueError(f"duplicate expected review rule: {rule_id}")
        expected.add(rule_id)

    if relationship_candidates is not None:
        parent = relationship_candidates.get("candidate_set", {}).get(
            "parent_contract", {}
        )
        contract_header = contract.get("contract", {})
        if (
            parent.get("id") != contract_header.get("id")
            or parent.get("version") != contract_header.get("version")
        ):
            raise ValueError(
                "relationship candidates must reference the reviewed contract "
                "ID and version"
            )
        candidates = relationship_candidates.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("relationship candidate set must contain candidates")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("relationship candidate must be a mapping")
            rule_id = candidate.get("candidate_rule_id")
            if not isinstance(rule_id, str) or not rule_id:
                raise ValueError("relationship candidate requires candidate_rule_id")
            if rule_id in expected:
                raise ValueError(f"duplicate expected review rule: {rule_id}")
            expected.add(rule_id)

    if not expected:
        raise ValueError("review instrument contains no expert-review rules")
    return tuple(sorted(expected))


def validate_review_coverage(
    response: dict[str, Any],
    *,
    expected_rule_ids: Iterable[str],
) -> None:
    """Reject paired-but-incomplete reviews before agreement is calculated."""

    expected = set(expected_rule_ids)
    observed = set(review_rule_ids(response))
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise ValueError(
            "review response does not cover the complete frozen review set; "
            f"missing={missing}, unexpected={unexpected}"
        )


def validate_review_operations(
    response: dict[str, Any],
    contract: dict[str, Any],
    *,
    relationship_candidates: dict[str, Any] | None = None,
) -> None:
    """Require an explicit accept/reject decision for every proposed operation."""

    proposed_operations: dict[str, set[str]] = {}
    for rule in contract.get("rules", []):
        if not isinstance(rule, dict) or rule.get("expert_review_required") is not True:
            continue
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str):
            continue
        operations = rule.get("allowed_operations", [])
        if not isinstance(operations, list) or not all(
            isinstance(operation, str) for operation in operations
        ):
            raise ValueError(f"rule {rule_id} has invalid allowed_operations")
        proposed_operations[rule_id] = set(operations)

    if relationship_candidates is not None:
        for candidate in relationship_candidates.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            rule_id = candidate.get("candidate_rule_id")
            if isinstance(rule_id, str):
                proposed_operations[rule_id] = set(
                    candidate.get("proposed_allowed_operations", [])
                )

    reviews = response.get("rule_reviews")
    if not isinstance(reviews, list):
        raise ValueError("rule_reviews must be a list")

    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("each rule review must be a mapping")
        rule_id = review.get("rule_id")
        if not isinstance(rule_id, str) or rule_id not in proposed_operations:
            continue
        accepted = review.get("accepted_operations")
        rejected = review.get("rejected_operations")
        if not isinstance(accepted, list) or not isinstance(rejected, list):
            raise ValueError(
                f"rule {rule_id} must explicitly list accepted and rejected operations"
            )
        accepted_set = set(accepted)
        rejected_set = set(rejected)
        overlap = accepted_set & rejected_set
        if overlap:
            raise ValueError(
                f"rule {rule_id} accepts and rejects the same operations: "
                f"{sorted(overlap)}"
            )
        proposed = proposed_operations[rule_id]
        if accepted_set | rejected_set != proposed:
            missing = sorted(proposed - (accepted_set | rejected_set))
            extra = sorted((accepted_set | rejected_set) - proposed)
            raise ValueError(
                f"rule {rule_id} operation review must partition the proposed "
                f"operations; missing={missing}, unexpected={extra}"
            )


def validate_complete_review_response(
    response: dict[str, Any],
    contract: dict[str, Any],
    *,
    relationship_candidates: dict[str, Any] | None = None,
) -> None:
    """Validate scientific review completeness beyond JSON-schema shape."""

    contract_key = _contract_key(response)
    header = contract.get("contract")
    if not isinstance(header, dict):
        raise ValueError("contract must contain contract metadata")
    expected_contract_key = (header.get("id"), header.get("version"))
    if contract_key != expected_contract_key:
        raise ValueError(
            "review response references a different contract ID or version"
        )

    expected = expected_review_rule_ids(
        contract,
        relationship_candidates=relationship_candidates,
    )
    validate_review_coverage(response, expected_rule_ids=expected)
    stage = response.get("review_stage", "legacy")
    if stage == "blind":
        return
    validate_review_operations(
        response,
        contract,
        relationship_candidates=relationship_candidates,
    )
