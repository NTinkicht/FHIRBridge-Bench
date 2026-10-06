"""Serialize in-memory semantic decisions into auditable schema records.

The classifier is intentionally independent of the repository's interchange
schema. This module is the narrow boundary that turns one classifier decision
into the frozen machine-readable record used for expert audit and reproducible
analysis.

Rule provenance is derived only from the compiled projectability policy and the
actual decision evidence. The emitter never invents aggregate rule identifiers.
If a primary-endpoint decision cannot be tied to at least one exact contract
rule, emission fails loudly instead of manufacturing provenance.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .classifier import SemanticDecision
from .model import LiftedFact
from .policy import VerificationPolicy

_EVIDENCE_FIELD_MAP = {
    "concept": "concept",
    "identifiers": "identifiers",
    "value": "value",
    "unit": "unit",
    "effective_time": "temporal.effective_start",
    "recorded_at": "temporal.recorded_at",
    "value_code": "attributes.value_code",
    "status": "attributes.status",
    "reference_range": "attributes.reference_range",
    "interpretation": "attributes.interpretation",
    "birthDate": "attributes.birthDate",
    "name": "attributes.name",
    "type_label": "attributes.type_label",
    "collection_method_label": "attributes.collection_method_label",
    "collection_quantity": "attributes.collection_quantity",
    "missing_relations": "relations",
}


def _source_fact(
    decision: SemanticDecision,
    source_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if len(decision.source_fact_ids) != 1:
        return None
    return source_by_id.get(decision.source_fact_ids[0])


def _target_fact(
    decision: SemanticDecision,
    target_by_id: dict[str, LiftedFact],
) -> LiftedFact | None:
    if len(decision.target_fact_ids) != 1:
        return None
    return target_by_id.get(decision.target_fact_ids[0])


def _field_from_decision(decision: SemanticDecision) -> str | None:
    omitted_field = decision.evidence.get("omitted_field")
    if isinstance(omitted_field, str):
        return omitted_field

    for evidence_key, policy_field in _EVIDENCE_FIELD_MAP.items():
        if evidence_key in decision.evidence:
            return policy_field

    if decision.classification == "MISATTRIBUTION":
        return "subject_ref"
    return None


def _all_fact_rule_ids(
    fact_type: str,
    policy: VerificationPolicy,
) -> tuple[str, ...]:
    fact_policy = policy.by_fact_type.get(fact_type)
    if fact_policy is None:
        return ()
    return fact_policy.rule_ids


def _required_fact_rule_ids(
    fact_type: str,
    policy: VerificationPolicy,
) -> tuple[str, ...]:
    rule_ids: set[str] = set()
    for field in policy.required_fields(fact_type):
        rule_ids.update(policy.rules_for_field(fact_type, field))
    return tuple(sorted(rule_ids))


def governing_rule_ids(
    decision: SemanticDecision,
    *,
    policy: VerificationPolicy,
    source_by_id: dict[str, dict[str, Any]],
) -> tuple[str, ...]:
    """Return exact contract rule IDs governing one classifier decision."""

    explicit = decision.evidence.get("rule_ids")
    if isinstance(explicit, list) and all(isinstance(item, str) for item in explicit):
        return tuple(sorted(set(explicit)))

    if decision.classification == "FABRICATION":
        return tuple(sorted(set(policy.must_not_infer_rule_ids)))

    source = _source_fact(decision, source_by_id)
    if source is None:
        return ()
    fact_type = source.get("fact_type")
    if not isinstance(fact_type, str):
        return ()

    field = _field_from_decision(decision)
    if field is not None:
        return policy.rules_for_field(fact_type, field)

    if decision.classification == "OMISSION":
        return _required_fact_rule_ids(fact_type, policy)

    if decision.classification in {
        "VERIFIED_EQUIVALENT",
        "LICENSED_NORMALIZATION",
        "LICENSED_DERIVATION",
        "DECLARED_LOSS",
    }:
        return _all_fact_rule_ids(fact_type, policy)

    return ()


def _target_paths(
    decision: SemanticDecision,
    target_by_id: dict[str, LiftedFact],
) -> list[str]:
    paths: set[str] = set()
    for target_id in decision.target_fact_ids:
        target = target_by_id.get(target_id)
        if target is not None:
            paths.update(target.target_paths)
    return sorted(paths)


def _parser_warnings(
    decision: SemanticDecision,
    target_by_id: dict[str, LiftedFact],
) -> list[str]:
    warnings: set[str] = set()
    for target_id in decision.target_fact_ids:
        target = target_by_id.get(target_id)
        if target is not None:
            warnings.update(target.parser_warnings)
    return sorted(warnings)


def emit_semantic_decision_record(
    decision: SemanticDecision,
    *,
    policy: VerificationPolicy,
    source_facts: list[dict[str, Any]],
    target_facts: list[LiftedFact],
    structural_validation_ref: str | None = None,
    model_claimed_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit one semantic-decision document conforming to the repository schema.

    This function is intentionally strict about endpoint rule provenance. An
    endpoint-eligible decision with no exact governing rule IDs indicates an
    instrument-scope bug and raises ``ValueError``.
    """

    source_by_id = {str(fact["fact_id"]): fact for fact in source_facts}
    target_by_id = {fact.lifted_fact_id: fact for fact in target_facts}
    rule_ids = governing_rule_ids(
        decision,
        policy=policy,
        source_by_id=source_by_id,
    )
    if decision.primary_endpoint_eligible and not rule_ids:
        raise ValueError(
            "primary-endpoint decision has no exact governing contract rule IDs: "
            f"{decision.decision_id}"
        )

    rationale_code = decision.evidence.get("rationale_code")
    if not isinstance(rationale_code, str) or not rationale_code:
        raise ValueError(
            f"decision lacks a machine-readable rationale_code: {decision.decision_id}"
        )

    source = _source_fact(decision, source_by_id)
    target = _target_fact(decision, target_by_id)
    evidence: dict[str, Any] = {
        "rationale_code": rationale_code,
        "parser_warnings": _parser_warnings(decision, target_by_id),
        "structural_validation_ref": structural_validation_ref,
        "decision_details": deepcopy(decision.evidence),
    }

    record: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "verifier_version": decision.verifier_version,
        "contract": {
            "contract_id": policy.contract_id,
            "contract_version": policy.contract_version,
            "rule_ids": list(rule_ids),
        },
        "source_fact_ids": list(decision.source_fact_ids),
        "target_fact_ids": list(decision.target_fact_ids),
        "target_paths": _target_paths(decision, target_by_id),
        "allowed_operation": None,
        "classification": decision.classification,
        "error_subtype": decision.error_subtype,
        "severity": decision.severity,
        "primary_endpoint_eligible": decision.primary_endpoint_eligible,
        "source_payload": deepcopy(source) if source is not None else None,
        "target_payload": deepcopy(target.semantic_payload) if target is not None else None,
        "evidence": evidence,
        "model_claimed_provenance": deepcopy(model_claimed_provenance),
        "explanation": None,
    }
    return record


def emit_classification_records(
    decisions: tuple[SemanticDecision, ...],
    *,
    policy: VerificationPolicy,
    source_facts: list[dict[str, Any]],
    target_facts: list[LiftedFact],
    structural_validation_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Emit a deterministically ordered audit record for every decision."""

    return [
        emit_semantic_decision_record(
            decision,
            policy=policy,
            source_facts=source_facts,
            target_facts=target_facts,
            structural_validation_ref=structural_validation_ref,
        )
        for decision in sorted(decisions, key=lambda item: item.decision_id)
    ]
