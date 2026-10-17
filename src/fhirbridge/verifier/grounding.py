"""Conservative source-to-target fact grounding.

Grounding establishes candidate support links before semantic equivalence is
scored. It deliberately prefers ambiguity over a guessed one-to-one match.
Model-emitted provenance is never used as grounding evidence here.

Representation-local identifiers (for example ``Patient/123`` versus a canonical
``patient-0001`` fact id) are never assumed to be equal. Entity/reference identity
is established independently and propagated through ``reference_map``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .model import GroundingCandidate, GroundingResult, LiftedFact


def _concept_key(fact: dict[str, Any]) -> tuple[object, object] | None:
    concept = fact.get("concept")
    if not isinstance(concept, dict):
        return None
    system = concept.get("system")
    code = concept.get("code")
    if system is None and code is None:
        return None
    return system, code


def _target_concept_key(fact: LiftedFact) -> tuple[object, object] | None:
    concept = fact.semantic_payload.get("concept")
    if not isinstance(concept, dict):
        return None
    system = concept.get("system")
    code = concept.get("code")
    if system is None and code is None:
        return None
    return system, code


def _identifier_keys(fact: dict[str, Any]) -> set[tuple[object, object]]:
    keys: set[tuple[object, object]] = set()
    identifiers = fact.get("identifiers", [])
    if not isinstance(identifiers, list):
        return keys
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            continue
        value = identifier.get("value")
        if value is None:
            continue
        keys.add((identifier.get("system"), value))
    return keys


def _target_identifier_keys(fact: LiftedFact) -> set[tuple[object, object]]:
    keys: set[tuple[object, object]] = set()
    identifiers = fact.semantic_payload.get("identifiers", [])
    if not isinstance(identifiers, list):
        return keys
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            continue
        value = identifier.get("value")
        if value is None:
            continue
        keys.add((identifier.get("system"), value))
    return keys


def _effective_time(fact: dict[str, Any]) -> object | None:
    temporal = fact.get("temporal")
    if not isinstance(temporal, dict):
        return None
    return temporal.get("effective_start")


def _target_effective_time(fact: LiftedFact) -> object | None:
    temporal = fact.semantic_payload.get("temporal")
    if not isinstance(temporal, dict):
        return None
    return temporal.get("effective_start")


def _relationship_set(fact: dict[str, Any]) -> set[tuple[str, str]]:
    relationships: set[tuple[str, str]] = set()
    raw = fact.get("relations", [])
    if not isinstance(raw, list):
        return relationships
    for relation in raw:
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("relation_type")
        target_fact_id = relation.get("target_fact_id")
        if isinstance(relation_type, str) and isinstance(target_fact_id, str):
            relationships.add((relation_type, target_fact_id))
    return relationships


def _translated_relationships(
    source: dict[str, Any],
    reference_map: Mapping[str, str],
) -> set[tuple[str, str]]:
    """Translate canonical relationship targets into target-local fact ids."""

    translated: set[tuple[str, str]] = set()
    for relation_type, canonical_target in _relationship_set(source):
        target_ref = reference_map.get(canonical_target)
        if target_ref is not None:
            translated.add((relation_type, target_ref))
    return translated


def score_candidate(
    source: dict[str, Any],
    target: LiftedFact,
    *,
    reference_map: Mapping[str, str] | None = None,
) -> GroundingCandidate | None:
    """Score one candidate grounding using conservative semantic keys.

    Fact type is mandatory. The score selects or exposes grounding ambiguity; it
    is never the semantic-fidelity outcome. Importantly, mismatched clinical
    content such as code or identifier is recorded as a conflict but is not
    automatically disqualifying: otherwise a corrupted fact would be converted
    into an omission+fabrication pair instead of being available for corruption
    classification.

    Subject/reference mismatches are penalized only after a representation-
    independent source→target reference mapping has already been established.
    """

    source_id = source.get("fact_id")
    source_type = source.get("fact_type")
    if not isinstance(source_id, str) or source_type != target.fact_type:
        return None

    refs = reference_map or {}
    score = 10
    matched: list[str] = ["fact_type"]
    conflicts: list[str] = []

    source_subject = source.get("subject_ref")
    target_subject = target.subject_ref
    if isinstance(source_subject, str) and target_subject is not None:
        expected_target_subject = refs.get(source_subject)
        if expected_target_subject is not None:
            if expected_target_subject == target_subject:
                score += 10
                matched.append("subject_identity")
            else:
                conflicts.append("subject_identity")
                score -= 20
        elif source_subject == target_subject:
            # Shared ids may occur in controlled fixtures, but raw id equality is
            # weak evidence and is never required across standards.
            score += 2
            matched.append("raw_subject_ref")

    source_concept = _concept_key(source)
    target_concept = _target_concept_key(target)
    if source_concept is not None and target_concept is not None:
        if source_concept == target_concept:
            score += 10
            matched.append("concept")
        else:
            conflicts.append("concept")

    source_identifiers = _identifier_keys(source)
    target_identifiers = _target_identifier_keys(target)
    if source_identifiers and target_identifiers:
        overlap = source_identifiers & target_identifiers
        if overlap:
            score += 12
            matched.append("identifier")
        else:
            conflicts.append("identifier")

    source_time = _effective_time(source)
    target_time = _target_effective_time(target)
    if source_time is not None and target_time is not None:
        if source_time == target_time:
            score += 6
            matched.append("effective_time")
        else:
            conflicts.append("effective_time")

    translated_relationships = _translated_relationships(source, refs)
    target_relationships = set(target.relationships)
    if translated_relationships and target_relationships:
        overlap = translated_relationships & target_relationships
        if overlap:
            score += min(8, 2 * len(overlap))
            matched.append("relationship")
        else:
            conflicts.append("relationship")

    return GroundingCandidate(
        source_fact_id=source_id,
        target_fact_id=target.lifted_fact_id,
        score=score,
        matched_keys=tuple(matched),
        conflicting_keys=tuple(conflicts),
    )


def ground_source_fact(
    source: dict[str, Any],
    targets: Iterable[LiftedFact],
    *,
    minimum_score: int = 10,
    reference_map: Mapping[str, str] | None = None,
) -> GroundingResult:
    """Ground one source fact to zero, one, or multiple target candidates.

    Ties at the highest score are reported as ambiguous. The verifier must not
    silently break these ties using renderer order, target paths, model claims,
    or a reference serialization.
    """

    source_id = source.get("fact_id")
    if not isinstance(source_id, str):
        raise ValueError("source fact requires a string fact_id")

    candidates = [
        candidate
        for target in targets
        if (
            candidate := score_candidate(
                source,
                target,
                reference_map=reference_map,
            )
        )
        is not None
        and candidate.score >= minimum_score
    ]
    candidates.sort(key=lambda item: (-item.score, item.target_fact_id))

    if not candidates:
        return GroundingResult(
            source_fact_id=source_id,
            target_fact_id=None,
            status="unmatched",
            rationale_code="NO_GROUNDING_CANDIDATE",
            candidates=(),
        )

    highest_score = candidates[0].score
    best = tuple(candidate for candidate in candidates if candidate.score == highest_score)
    if len(best) > 1:
        return GroundingResult(
            source_fact_id=source_id,
            target_fact_id=None,
            status="ambiguous",
            rationale_code="TIED_GROUNDING_CANDIDATES",
            candidates=best,
            evidence={"highest_score": highest_score},
        )

    winner = best[0]
    return GroundingResult(
        source_fact_id=source_id,
        target_fact_id=winner.target_fact_id,
        status="grounded",
        rationale_code="UNIQUE_BEST_GROUNDING",
        candidates=tuple(candidates),
        evidence={
            "score": winner.score,
            "matched_keys": list(winner.matched_keys),
            "conflicting_keys": list(winner.conflicting_keys),
        },
    )


def _grounding_priority(source: dict[str, Any]) -> tuple[int, str]:
    """Ground identity/context facts before dependent observations."""

    fact_type = str(source.get("fact_type", ""))
    priority = {
        "patient_identity": 0,
        "diagnostic_report": 1,
        "order": 1,
        "specimen": 2,
        "encounter": 2,
        "observation": 3,
    }.get(fact_type, 4)
    return priority, str(source.get("fact_id", ""))


def ground_graph(
    source_facts: Iterable[dict[str, Any]],
    target_facts: Iterable[LiftedFact],
    *,
    minimum_score: int = 10,
) -> dict[str, GroundingResult]:
    """Ground a source graph while propagating representation-independent refs.

    Facts are processed in a stable context-first order. Each uniquely grounded
    source fact adds ``canonical fact id → target-local lifted fact id`` to the
    reference map used by later facts. This lets an Observation whose canonical
    subject is ``patient-0001`` match a target Observation whose subject is
    ``Patient/abc`` once the patient facts have independently been grounded by
    identifiers.

    One-to-many and many-to-one semantics are not forced here; ambiguous cases
    remain explicit for contract-aware handling later.
    """

    source_list = sorted(list(source_facts), key=_grounding_priority)
    target_list = list(target_facts)
    reference_map: dict[str, str] = {}
    results: dict[str, GroundingResult] = {}

    for source in source_list:
        source_id = source.get("fact_id")
        if not isinstance(source_id, str):
            raise ValueError("every source fact requires a string fact_id")

        result = ground_source_fact(
            source,
            target_list,
            minimum_score=minimum_score,
            reference_map=reference_map,
        )
        results[source_id] = result
        if result.status == "grounded" and result.target_fact_id is not None:
            reference_map[source_id] = result.target_fact_id

    return results
