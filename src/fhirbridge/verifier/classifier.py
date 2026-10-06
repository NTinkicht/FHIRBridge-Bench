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

_VERIFIER_VERSION = "0.4.0-dev"


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


def _absence_is_scoreable(
    policy: VerificationPolicy | None,
    source: dict[str, Any],
) -> bool:
    """Whether absence of the whole source fact can drive the primary endpoint."""

    if policy is None:
        return True
    fact_type = source.get("fact_type")
    return isinstance(fact_type, str) and policy.has_required_scope(fact_type)


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

    # Relationship semantics are scored only when the contract explicitly places
    # them in scope. With no VerificationPolicy, development diagnostics preserve
    # the broad relationship check.
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


def _ambiguity_implies_absence(
    source: dict[str, Any],
    grounding: GroundingResult,
    *,
    policy: VerificationPolicy | None,
) -> bool:
    """Return true when every tied candidate contradicts a scored identity key.

    A conflict in an unscored identifier or concept must not create a
    confirmatory omission. This prevents grounding heuristics from enlarging the
    measurement construct beyond the projectability contract.
    """

    if not grounding.candidates:
        return False

    source_has_concept = _concept_key(source) is not None
    source_has_identifier = bool(_identifier_set(source))

    if (
        source_has_concept
        and _scores(policy, source, "concept")
        and all("concept" in candidate.conflicting_keys for candidate in grounding.candidates)
    ):
        return True
    if (
        source_has_identifier
        and _scores(policy, source, "identifiers")
        and all("identifier" in candidate.conflicting_keys for candidate in grounding.candidates)
    ):
        return True
    return False


def _looks_misattributed(
    source: dict[str, Any],
    targets: list[LiftedFact],
    *,
    reference_map: dict[str, str],
    policy: VerificationPolicy | None,
) -> LiftedFact | None:
    """Find one strong same-fact candidate whose subject attribution conflicts.

    Under a contract-scoped analysis, only evidence dimensions that are in the
    comparison scope may make the candidate strong enough to stand in for the
    source fact. Subject mismatch itself is handled separately so it can remain
    diagnostic-only until a reviewed subject-attribution rule exists.
    """

    matched_key_to_field = {
        "concept": "concept",
        "identifier": "identifiers",
        "effective_time": "temporal.effective_start",
        "relationship": "relations",
    }
    candidates: list[tuple[int, LiftedFact]] = []
    for target in targets:
        candidate = score_candidate(source, target, reference_map=reference_map)
        if candidate is None or "subject_identity" not in candidate.conflicting_keys:
            continue
        strong_keys = {
            key
            for key, field in matched_key_to_field.items()
            if policy is None or _scores(policy, source, field)
        }
        if not (strong_keys & set(candidate.matched_keys)):
            continue
        candidates.append((candidate.score, target))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1].lifted_fact_id))
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return candidates[0][1]


def _pair_decision(
    source: dict[str, Any],
    target: LiftedFact,
    *,
    reference_map: dict[str, str],
    grounding: GroundingResult,
    policy: VerificationPolicy | None,
    scope_note: str | None = None,
) -> SemanticDecision:
    """Build the corruption/equivalence decision for one supported fact pair."""

    source_id = str(source["fact_id"])
    subtype, evidence = _compare_grounded_fact(
        source,
        target,
        reference_map=reference_map,
        grounding=grounding,
        policy=policy,
    )
    if scope_note is not None:
        evidence = {**evidence, "scope_note": scope_note}

    if subtype is not None:
        severity = "S3" if subtype in {"value", "unit", "identifier"} else "S2"
        return SemanticDecision(
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

    return SemanticDecision(
        decision_id=f"{source_id}:verified",
        classification="VERIFIED_EQUIVALENT",
        source_fact_ids=(source_id,),
        target_fact_ids=(target.lifted_fact_id,),
        severity="S0",
        evidence={"rationale_code": "FACT_SEMANTICS_PRESERVED", **evidence},
    )


def _unscored_absence_decision(
    source: dict[str, Any],
    *,
    rationale_code: str,
    extra_evidence: dict[str, Any] | None = None,
) -> SemanticDecision:
    source_id = str(source["fact_id"])
    return SemanticDecision(
        decision_id=f"{source_id}:indeterminate:out_of_scope_absence",
        classification="INDETERMINATE",
        source_fact_ids=(source_id,),
        primary_endpoint_eligible=False,
        evidence={
            "rationale_code": rationale_code,
            "scope_note": "NO_REQUIRED_PROJECTABILITY_RULE_FOR_WHOLE_FACT_ABSENCE",
            **(extra_evidence or {}),
        },
    )


def classify_graph(
    source_facts: list[dict[str, Any]],
    target_facts: list[LiftedFact],
    *,
    minimum_grounding_score: int = 10,
    policy: VerificationPolicy | None = None,
) -> ClassificationResult:
    """Classify semantic outcomes for one canonical source and lifted target.

    Development diagnostics preserve precedence MISATTRIBUTION > CORRUPTION >
    OMISSION > FABRICATION. In contract-scoped analysis, that precedence applies
    only to dimensions explicitly licensed by the projectability contract.
    Grounding may use additional context to find candidates, but unlicensed
    context cannot by itself create a primary semantic-fidelity failure.
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
        source_id = str(source["fact_id"])
        result = grounding[source_id]

        if result.status == "ambiguous":
            if _ambiguity_implies_absence(source, result, policy=policy):
                evidence = {
                    "rationale_code": "NO_SEMANTICALLY_COMPATIBLE_TIED_CANDIDATE",
                    "candidate_ids": [c.target_fact_id for c in result.candidates],
                }
                if _absence_is_scoreable(policy, source):
                    decisions.append(
                        SemanticDecision(
                            decision_id=f"{source_id}:omission",
                            classification="OMISSION",
                            source_fact_ids=(source_id,),
                            error_subtype="other",
                            severity=(
                                "S3"
                                if source.get("fact_type") == "observation"
                                else "S2"
                            ),
                            evidence=evidence,
                        )
                    )
                else:
                    decisions.append(
                        _unscored_absence_decision(
                            source,
                            rationale_code="AMBIGUOUS_FACT_ABSENCE_OUTSIDE_REQUIRED_SCOPE",
                            extra_evidence=evidence,
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
            subject_conflict_candidate = _looks_misattributed(
                source,
                target_facts,
                reference_map=reference_map,
                policy=policy,
            )
            if subject_conflict_candidate is not None:
                used_target_ids.add(subject_conflict_candidate.lifted_fact_id)
                if _scores(policy, source, "subject_ref"):
                    decisions.append(
                        SemanticDecision(
                            decision_id=f"{source_id}:misattribution",
                            classification="MISATTRIBUTION",
                            source_fact_ids=(source_id,),
                            target_fact_ids=(subject_conflict_candidate.lifted_fact_id,),
                            error_subtype="attribution",
                            severity="S3",
                            evidence={
                                "rationale_code": "WRONG_SUBJECT_ATTRIBUTION",
                                "target_subject_ref": subject_conflict_candidate.subject_ref,
                            },
                        )
                    )
                else:
                    decisions.append(
                        _pair_decision(
                            source,
                            subject_conflict_candidate,
                            reference_map=reference_map,
                            grounding=result,
                            policy=policy,
                            scope_note="SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE",
                        )
                    )
            elif _absence_is_scoreable(policy, source):
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
            else:
                decisions.append(
                    _unscored_absence_decision(
                        source,
                        rationale_code="NO_GROUNDING_CANDIDATE_OUTSIDE_REQUIRED_SCOPE",
                    )
                )
            continue

        assert result.target_fact_id is not None
        target = target_by_id[result.target_fact_id]
        used_target_ids.add(target.lifted_fact_id)

        conflicts = set(result.evidence.get("conflicting_keys", []))
        if "subject_identity" in conflicts and _scores(policy, source, "subject_ref"):
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

        scope_note = None
        if "subject_identity" in conflicts and not _scores(policy, source, "subject_ref"):
            scope_note = "SUBJECT_ATTRIBUTION_OUTSIDE_CONTRACT_SCOPE"
        decisions.append(
            _pair_decision(
                source,
                target,
                reference_map=reference_map,
                grounding=result,
                policy=policy,
                scope_note=scope_note,
            )
        )

    for target in target_facts:
        if target.lifted_fact_id in used_target_ids:
            continue
        if policy is not None and not policy.forbids_ungrounded_inference:
            decisions.append(
                SemanticDecision(
                    decision_id=f"{target.lifted_fact_id}:indeterminate:unsupported_target",
                    classification="INDETERMINATE",
                    target_fact_ids=(target.lifted_fact_id,),
                    primary_endpoint_eligible=False,
                    evidence={
                        "rationale_code": "NO_MUST_NOT_INFER_RULE_FOR_UNSUPPORTED_TARGET",
                        "contract_id": policy.contract_id,
                        "contract_version": policy.contract_version,
                    },
                )
            )
            continue

        fabrication_evidence: dict[str, Any] = {
            "rationale_code": "UNSUPPORTED_TARGET_FACT"
        }
        if policy is not None:
            fabrication_evidence.update(
                {
                    "contract_id": policy.contract_id,
                    "contract_version": policy.contract_version,
                    "rule_ids": list(policy.must_not_infer_rule_ids),
                }
            )
        decisions.append(
            SemanticDecision(
                decision_id=f"{target.lifted_fact_id}:fabrication",
                classification="FABRICATION",
                target_fact_ids=(target.lifted_fact_id,),
                error_subtype="unsupported_assertion",
                severity="S2",
                evidence=fabrication_evidence,
            )
        )

    decisions.sort(key=lambda decision: decision.decision_id)
    return ClassificationResult(decisions=tuple(decisions), grounding=grounding)
