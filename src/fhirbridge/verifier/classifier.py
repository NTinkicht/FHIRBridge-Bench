"""Deterministic fact-level semantic classification for verifier qualification.

The classifier consumes canonical source facts and independently lifted target
facts. It is deliberately standard-independent: FHIR paths and HL7 v2 field
positions belong in lifters, not here.

This module implements the development-stage exact-equivalence baseline. It does
not yet claim ConceptMap or UCUM-conversion support; those providers are added at
the equivalence layer before Protocol v1.0 qualification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .equivalence import instants_equivalent
from .grounding import ground_graph, score_candidate
from .model import GroundingResult, LiftedFact
from .policy import VerificationPolicy

_VERIFIER_VERSION = "0.3.0-dev"


@dataclass(frozen=True)
class SemanticDecision:
    """One machine-readable fact-level semantic decision."""

    decision_id: str
    classification: str
    source_fact_ids: tuple[str, ...] = ()
    target_fact_ids: tuple[str, ...] = ()
    error_subtype: str | None = None
    severity: str | None = None
    primary_endpoint_eligible: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)
    verifier_version: str = _VERIFIER_VERSION

    def __post_init__(self) -> None:
        allowed = {
            "VERIFIED_EQUIVALENT",
            "LICENSED_NORMALIZATION",
            "LICENSED_DERIVATION",
            "DECLARED_LOSS",
            "FABRICATION",
            "CORRUPTION",
            "OMISSION",
            "MISATTRIBUTION",
            "INDETERMINATE",
            "STRUCTURAL_ERROR",
        }
        if self.classification not in allowed:
            raise ValueError(f"unsupported semantic classification: {self.classification}")


@dataclass(frozen=True)
class ClassificationResult:
    """All semantic decisions for one source/target artifact pair."""

    decisions: tuple[SemanticDecision, ...]
    grounding: dict[str, GroundingResult]

    @property
    def faithful(self) -> bool:
        """Whether all primary-endpoint-eligible decisions preserve semantics."""

        failures = {"FABRICATION", "CORRUPTION", "OMISSION", "MISATTRIBUTION"}
        return not any(
            decision.primary_endpoint_eligible and decision.classification in failures
            for decision in self.decisions
        )


def _identifier_set(payload: dict[str, Any]) -> set[tuple[object, object, object]]:
    identifiers = payload.get("identifiers", [])
    if not isinstance(identifiers, list):
        return set()
    result: set[tuple[object, object, object]] = set()
    for identifier in identifiers:
        if isinstance(identifier, dict) and identifier.get("value") is not None:
            result.add(
                (
                    identifier.get("system"),
                    identifier.get("value"),
                    identifier.get("type"),
                )
            )
    return result


def _concept_key(payload: dict[str, Any]) -> tuple[object, object] | None:
    concept = payload.get("concept")
    if not isinstance(concept, dict):
        return None
    system = concept.get("system")
    code = concept.get("code")
    if system is None and code is None:
        return None
    return system, code


def _coded_value_key(attributes: dict[str, Any]) -> tuple[object, object] | None:
    coded_value = attributes.get("value_code")
    if not isinstance(coded_value, dict):
        return None
    system = coded_value.get("system")
    code = coded_value.get("code")
    if system is None and code is None:
        return None
    return system, code


def _temporal_value(payload: dict[str, Any], key: str) -> object | None:
    temporal = payload.get("temporal")
    if not isinstance(temporal, dict):
        return None
    return temporal.get(key)


def _same_time(source: object | None, target: object | None) -> bool:
    if source == target:
        return True
    if not isinstance(source, str) or not isinstance(target, str):
        return False
    if "T" not in source or "T" not in target:
        return False
    try:
        return instants_equivalent(source, target).equivalent
    except ValueError:
        return False


def _relation_set(payload: dict[str, Any]) -> set[tuple[str, str]]:
    relations = payload.get("relations", [])
    if not isinstance(relations, list):
        return set()
    result: set[tuple[str, str]] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("relation_type")
        target_fact_id = relation.get("target_fact_id")
        if isinstance(relation_type, str) and isinstance(target_fact_id, str):
            result.add((relation_type, target_fact_id))
    return result


def _translated_required_relations(
    source: dict[str, Any], reference_map: dict[str, str]
) -> set[tuple[str, str]]:
    translated: set[tuple[str, str]] = set()
    for relation_type, canonical_target in _relation_set(source):
        target_local = reference_map.get(canonical_target)
        if target_local is not None:
            translated.add((relation_type, target_local))
    return translated


def _scores(
    policy: VerificationPolicy | None,
    source: dict[str, Any],
    field: str,
) -> bool:
    if policy is None:
        return True
    fact_type = source.get("fact_type")
    return isinstance(fact_type, str) and policy.scores(fact_type, field)


def _compare_grounded_fact(
    source: dict[str, Any],
    target: LiftedFact,
    *,
    reference_map: dict[str, str],
    grounding: GroundingResult,
    policy: VerificationPolicy | None,
) -> tuple[str | None, dict[str, Any]]:
    """Return the first deterministic semantic mismatch, if any.

    The order is intentional and stable. Attribution is handled before this
    function. For ordinary corruption we prefer clinically concrete subtypes
    over a generic payload-difference label. When ``policy`` is supplied, only
    fields declared projectable by the contract are scored.
    """

    target_payload = target.semantic_payload
    checks: dict[str, Any] = {}

    if _scores(policy, source, "concept"):
        source_concept = _concept_key(source)
        target_concept = _concept_key(target_payload)
        if source_concept != target_concept:
            checks["concept"] = {"source": source_concept, "target": target_concept}
            return "terminology", checks

    if _scores(policy, source, "identifiers"):
        source_identifiers = _identifier_set(source)
        target_identifiers = _identifier_set(target_payload)
        if source_identifiers != target_identifiers:
            checks["identifiers"] = {
                "source": sorted(map(str, source_identifiers)),
                "target": sorted(map(str, target_identifiers)),
            }
            return "identifier", checks

    if _scores(policy, source, "value"):
        source_value = source.get("value")
        target_value = target_payload.get("value")
        if source_value != target_value:
            checks["value"] = {"source": source_value, "target": target_value}
            return "value", checks

    if _scores(policy, source, "unit"):
        source_unit = source.get("unit")
        target_unit = target_payload.get("unit")
        if source_unit != target_unit:
            checks["unit"] = {"source": source_unit, "target": target_unit}
            return "unit", checks

    if _scores(policy, source, "temporal.effective_start"):
        source_effective = _temporal_value(source, "effective_start")
        target_effective = _temporal_value(target_payload, "effective_start")
        if not _same_time(source_effective, target_effective):
            checks["effective_time"] = {
                "source": source_effective,
                "target": target_effective,
            }
            return "temporal", checks

    if _scores(policy, source, "temporal.recorded_at"):
        source_recorded = _temporal_value(source, "recorded_at")
        target_recorded = _temporal_value(target_payload, "recorded_at")
        if not _same_time(source_recorded, target_recorded):
            checks["recorded_at"] = {"source": source_recorded, "target": target_recorded}
            return "temporal", checks

    source_attributes = (
        source.get("attributes") if isinstance(source.get("attributes"), dict) else {}
    )
    target_attributes = (
        target_payload.get("attributes")
        if isinstance(target_payload.get("attributes"), dict)
        else {}
    )

    if _scores(policy, source, "attributes.value_code"):
        source_value_code = _coded_value_key(source_attributes)
        target_value_code = _coded_value_key(target_attributes)
        if source_value_code != target_value_code:
            checks["value_code"] = {"source": source_value_code, "target": target_value_code}
            return "terminology", checks

    attribute_subtypes = {
        "status": "status",
        "reference_range": "other",
        "interpretation": "other",
        "birthDate": "other",
        "name": "other",
        "type_label": "terminology",
        "collection_method_label": "terminology",
        "collection_quantity": "unit",
    }
    for key, subtype in attribute_subtypes.items():
        policy_field = f"attributes.{key}"
        if not _scores(policy, source, policy_field):
            continue
        if source_attributes.get(key) != target_attributes.get(key):
            checks[key] = {
                "source": source_attributes.get(key),
                "target": target_attributes.get(key),
            }
            return subtype, checks

    # Relationship semantics are scored only when the frozen contract explicitly
    # places them in scope. With no VerificationPolicy, development diagnostics
    # preserve the previous broad relationship check. This prevents an
    # implementation-local graph edge from silently becoming confirmatory truth.
    if _scores(policy, source, "relations"):
        required_relations = _translated_required_relations(source, reference_map)
        target_relations = set(target.relationships)
        missing_relations = required_relations - target_relations
        if missing_relations:
            checks["missing_relations"] = sorted(missing_relations)
            return "relationship", checks

    checks["grounding"] = grounding.evidence
    if policy is not None:
        checks["verification_policy"] = {
            "contract_id": policy.contract_id,
            "contract_version": policy.contract_version,
        }
    return None, checks


def _ambiguity_implies_absence(source: dict[str, Any], grounding: GroundingResult) -> bool:
    """Return true when every tied candidate contradicts a strong identity key.

    This lets a missing panel member be classified as an omission when the only
    remaining same-type candidates all carry different observation concepts.
    It never selects one of the tied candidates.
    """

    if not grounding.candidates:
        return False

    source_has_concept = _concept_key(source) is not None
    source_has_identifier = bool(_identifier_set(source))

    if source_has_concept and all(
        "concept" in candidate.conflicting_keys for candidate in grounding.candidates
    ):
        return True
    if source_has_identifier and all(
        "identifier" in candidate.conflicting_keys for candidate in grounding.candidates
    ):
        return True
    return False


def _looks_misattributed(
    source: dict[str, Any],
    targets: list[LiftedFact],
    *,
    reference_map: dict[str, str],
) -> LiftedFact | None:
    """Find one strong same-fact candidate whose subject attribution conflicts."""

    candidates: list[tuple[int, LiftedFact]] = []
    for target in targets:
        candidate = score_candidate(source, target, reference_map=reference_map)
        if candidate is None or "subject_identity" not in candidate.conflicting_keys:
            continue
        strong_keys = {"concept", "identifier", "effective_time", "relationship"}
        if not (strong_keys & set(candidate.matched_keys)):
            continue
        candidates.append((candidate.score, target))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1].lifted_fact_id))
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return candidates[0][1]


def classify_graph(
    source_facts: list[dict[str, Any]],
    target_facts: list[LiftedFact],
    *,
    minimum_grounding_score: int = 10,
    policy: VerificationPolicy | None = None,
) -> ClassificationResult:
    """Classify semantic outcomes for one canonical source and lifted target.

    Precedence is enforced as MISATTRIBUTION > CORRUPTION > OMISSION >
    FABRICATION. Extra target facts are therefore considered fabrication only
    after all source facts have had an opportunity to ground or be recognized as
    misattributed. When provided, ``policy`` limits field comparisons to the
    projectability contract while preserving independent grounding evidence.
    """

    grounding = ground_graph(
        source_facts,
        target_facts,
        minimum_score=minimum_grounding_score,
    )
    target_by_id = {fact.lifted_fact_id: fact for fact in target_facts}
    reference_map = {
        source_id: result.target_fact_id
        for source_id, result in grounding.items()
        if result.status == "grounded" and result.target_fact_id is not None
    }

    used_target_ids: set[str] = set()
    decisions: list[SemanticDecision] = []

    for source in source_facts:
        source_id = source["fact_id"]
        result = grounding[source_id]

        if result.status == "ambiguous":
            if _ambiguity_implies_absence(source, result):
                decisions.append(
                    SemanticDecision(
                        decision_id=f"{source_id}:omission",
                        classification="OMISSION",
                        source_fact_ids=(source_id,),
                        error_subtype="other",
                        severity=(
                            "S3" if source.get("fact_type") == "observation" else "S2"
                        ),
                        evidence={
                            "rationale_code": "NO_SEMANTICALLY_COMPATIBLE_TIED_CANDIDATE",
                            "candidate_ids": [c.target_fact_id for c in result.candidates],
                        },
                    )
                )
            else:
                decisions.append(
                    SemanticDecision(
                        decision_id=f"{source_id}:indeterminate",
                        classification="INDETERMINATE",
                        source_fact_ids=(source_id,),
                        primary_endpoint_eligible=False,
                        evidence={
                            "rationale_code": result.rationale_code,
                            "candidate_ids": [c.target_fact_id for c in result.candidates],
                        },
                    )
                )
            continue

        if result.status == "unmatched":
            misattributed = _looks_misattributed(
                source,
                target_facts,
                reference_map=reference_map,
            )
            if misattributed is not None:
                used_target_ids.add(misattributed.lifted_fact_id)
                decisions.append(
                    SemanticDecision(
                        decision_id=f"{source_id}:misattribution",
                        classification="MISATTRIBUTION",
                        source_fact_ids=(source_id,),
                        target_fact_ids=(misattributed.lifted_fact_id,),
                        error_subtype="attribution",
                        severity="S3",
                        evidence={
                            "rationale_code": "WRONG_SUBJECT_ATTRIBUTION",
                            "target_subject_ref": misattributed.subject_ref,
                        },
                    )
                )
            else:
                decisions.append(
                    SemanticDecision(
                        decision_id=f"{source_id}:omission",
                        classification="OMISSION",
                        source_fact_ids=(source_id,),
                        error_subtype="other",
                        severity=(
                            "S3" if source.get("fact_type") == "observation" else "S2"
                        ),
                        evidence={"rationale_code": result.rationale_code},
                    )
                )
            continue

        assert result.target_fact_id is not None
        target = target_by_id[result.target_fact_id]
        used_target_ids.add(target.lifted_fact_id)

        conflicts = set(result.evidence.get("conflicting_keys", []))
        if "subject_identity" in conflicts:
            decisions.append(
                SemanticDecision(
                    decision_id=f"{source_id}:misattribution",
                    classification="MISATTRIBUTION",
                    source_fact_ids=(source_id,),
                    target_fact_ids=(target.lifted_fact_id,),
                    error_subtype="attribution",
                    severity="S3",
                    evidence={
                        "rationale_code": "WRONG_SUBJECT_ATTRIBUTION",
                        "grounding": result.evidence,
                    },
                )
            )
            continue

        subtype, evidence = _compare_grounded_fact(
            source,
            target,
            reference_map=reference_map,
            grounding=result,
            policy=policy,
        )
        if subtype is not None:
            severity = "S3" if subtype in {"value", "unit", "identifier"} else "S2"
            decisions.append(
                SemanticDecision(
                    decision_id=f"{source_id}:corruption:{subtype}",
                    classification="CORRUPTION",
                    source_fact_ids=(source_id,),
                    target_fact_ids=(target.lifted_fact_id,),
                    error_subtype=subtype,
                    severity=severity,
                    evidence={
                        "rationale_code": f"SEMANTIC_{subtype.upper()}_MISMATCH",
                        **evidence,
                    },
                )
            )
        else:
            decisions.append(
                SemanticDecision(
                    decision_id=f"{source_id}:verified",
                    classification="VERIFIED_EQUIVALENT",
                    source_fact_ids=(source_id,),
                    target_fact_ids=(target.lifted_fact_id,),
                    severity="S0",
                    evidence={"rationale_code": "FACT_SEMANTICS_PRESERVED", **evidence},
                )
            )

    for target in target_facts:
        if target.lifted_fact_id in used_target_ids:
            continue
        decisions.append(
            SemanticDecision(
                decision_id=f"{target.lifted_fact_id}:fabrication",
                classification="FABRICATION",
                target_fact_ids=(target.lifted_fact_id,),
                error_subtype="unsupported_assertion",
                severity="S2",
                evidence={"rationale_code": "UNSUPPORTED_TARGET_FACT"},
            )
        )

    decisions.sort(key=lambda decision: decision.decision_id)
    return ClassificationResult(decisions=tuple(decisions), grounding=grounding)
