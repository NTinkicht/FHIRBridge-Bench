"""Conservative source-to-target fact grounding.

Grounding establishes candidate support links before semantic equivalence is
scored. It deliberately prefers ambiguity over a guessed one-to-one match.
Model-emitted provenance is never used as grounding evidence here.
"""

from __future__ import annotations

from collections.abc import Iterable
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


def score_candidate(source: dict[str, Any], target: LiftedFact) -> GroundingCandidate | None:
    """Score one candidate grounding using only conservative semantic keys.

    Fact type is mandatory. Other keys increase confidence but are not treated as
    correctness evidence. The score is used only to select or expose grounding
    ambiguity, never as the semantic-fidelity score.
    """

    source_id = source.get("fact_id")
    source_type = source.get("fact_type")
    if not isinstance(source_id, str) or source_type != target.fact_type:
        return None

    score = 10
    matched: list[str] = ["fact_type"]
    conflicts: list[str] = []

    source_subject = source.get("subject_ref")
    target_subject = target.subject_ref
    if source_subject is not None and target_subject is not None:
        if source_subject == target_subject:
            score += 8
            matched.append("subject_ref")
        else:
            conflicts.append("subject_ref")
            score -= 12

    source_concept = _concept_key(source)
    target_concept = _target_concept_key(target)
    if source_concept is not None and target_concept is not None:
        if source_concept == target_concept:
            score += 12
            matched.append("concept")
        else:
            conflicts.append("concept")
            score -= 8

    source_identifiers = _identifier_keys(source)
    target_identifiers = _target_identifier_keys(target)
    if source_identifiers and target_identifiers:
        overlap = source_identifiers & target_identifiers
        if overlap:
            score += 14
            matched.append("identifier")
        else:
            conflicts.append("identifier")
            score -= 10

    source_time = _effective_time(source)
    target_time = _target_effective_time(target)
    if source_time is not None and target_time is not None:
        if source_time == target_time:
            score += 6
            matched.append("effective_time")
        else:
            conflicts.append("effective_time")

    source_relationships = _relationship_set(source)
    target_relationships = set(target.relationships)
    if source_relationships and target_relationships:
        overlap = source_relationships & target_relationships
        if overlap:
            score += min(6, 2 * len(overlap))
            matched.append("relationship")

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
) -> GroundingResult:
    """Ground one source fact to zero, one, or multiple target candidates.

    Ties at the highest score are reported as ambiguous. The verifier must not
    silently break these ties using renderer order, target paths, or model claims.
    """

    source_id = source.get("fact_id")
    if not isinstance(source_id, str):
        raise ValueError("source fact requires a string fact_id")

    candidates = [
        candidate
        for target in targets
        if (candidate := score_candidate(source, target)) is not None
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


def ground_graph(
    source_facts: Iterable[dict[str, Any]],
    target_facts: Iterable[LiftedFact],
    *,
    minimum_score: int = 10,
) -> dict[str, GroundingResult]:
    """Ground all source facts without enforcing one-to-one target ownership.

    One-to-many and many-to-one semantics are handled later under explicit
    contract rules. This function therefore avoids prematurely consuming target
    facts as if every transformation were one-to-one.
    """

    target_list = list(target_facts)
    return {
        str(source["fact_id"]): ground_source_fact(
            source,
            target_list,
            minimum_score=minimum_score,
        )
        for source in source_facts
    }
