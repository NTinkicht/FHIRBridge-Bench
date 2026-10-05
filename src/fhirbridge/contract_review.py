"""Utilities for preserving and comparing independent contract reviews.

The comparison layer treats original reviewer decisions as immutable inputs. It
computes agreement and surfaces disagreements but does not adjudicate or rewrite
reviewer labels.
"""

from __future__ import annotations

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
