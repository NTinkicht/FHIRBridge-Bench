"""Contract-aware refinement of base semantic classification.

The base classifier detects semantic mismatches without assuming a target
standard. This refinement uses only the already-compiled projectability policy
to distinguish an absent required source field from an altered present field.
It does not inspect FHIR paths, HL7 fields, renderer code, or the raw contract.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .classifier import (
    ClassificationResult,
    SemanticDecision,
    classify_graph as _classify_graph_base,
)
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
}

_REQUIRED_PROJECTABILITY = {"MUST_PRESERVE", "MAY_TRANSFORM"}


def _present(value: Any) -> bool:
    return value is not None and value not in {""}


def _mismatch_field(decision: SemanticDecision) -> tuple[str, Any, Any] | None:
    for evidence_key, policy_field in _EVIDENCE_FIELD_MAP.items():
        mismatch = decision.evidence.get(evidence_key)
        if not isinstance(mismatch, dict):
            continue
        if "source" not in mismatch or "target" not in mismatch:
            continue
        return policy_field, mismatch.get("source"), mismatch.get("target")
    return None


def _refine_required_field_omission(
    decision: SemanticDecision,
    *,
    source_by_id: dict[str, dict[str, Any]],
    policy: VerificationPolicy,
) -> SemanticDecision:
    if decision.classification != "CORRUPTION" or len(decision.source_fact_ids) != 1:
        return decision
    mismatch = _mismatch_field(decision)
    if mismatch is None:
        return decision
    field, source_value, target_value = mismatch
    if not _present(source_value) or _present(target_value):
        return decision

    source_id = decision.source_fact_ids[0]
    source = source_by_id.get(source_id)
    if source is None:
        return decision
    fact_type = source.get("fact_type")
    if not isinstance(fact_type, str):
        return decision
    projectability = policy.projectability(fact_type, field)
    if projectability not in _REQUIRED_PROJECTABILITY:
        return decision

    evidence = dict(decision.evidence)
    evidence.update(
        {
            "rationale_code": "REQUIRED_PROJECTABLE_FIELD_ABSENT",
            "omitted_field": field,
            "projectability": projectability,
            "contract_id": policy.contract_id,
            "contract_version": policy.contract_version,
        }
    )
    return replace(
        decision,
        decision_id=f"{source_id}:omission:{field.replace('.', '_')}",
        classification="OMISSION",
        evidence=evidence,
    )


def classify_graph(
    source_facts: list[dict[str, Any]],
    target_facts: list[LiftedFact],
    *,
    minimum_grounding_score: int = 10,
    policy: VerificationPolicy | None = None,
) -> ClassificationResult:
    """Classify a graph and refine required-field absence under the contract."""

    result = _classify_graph_base(
        source_facts,
        target_facts,
        minimum_grounding_score=minimum_grounding_score,
        policy=policy,
    )
    if policy is None:
        return result

    source_by_id = {fact["fact_id"]: fact for fact in source_facts}
    decisions = tuple(
        _refine_required_field_omission(
            decision,
            source_by_id=source_by_id,
            policy=policy,
        )
        for decision in result.decisions
    )
    return ClassificationResult(
        decisions=tuple(sorted(decisions, key=lambda item: item.decision_id)),
        grounding=result.grounding,
    )
