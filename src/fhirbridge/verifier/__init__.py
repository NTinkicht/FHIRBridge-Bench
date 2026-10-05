"""Standard-independent semantic verification utilities."""

from .classifier import ClassificationResult, SemanticDecision, classify_graph
from .equivalence import (
    EquivalenceResult,
    ExactTerminologyEquivalence,
    ExactUnitEquivalence,
    TerminologyEquivalenceProvider,
    UnitEquivalenceProvider,
    identifiers_equivalent,
    instants_equivalent,
)
from .grounding import ground_graph, ground_source_fact, score_candidate
from .model import GroundingCandidate, GroundingResult, LiftedFact

__all__ = [
    "ClassificationResult",
    "EquivalenceResult",
    "ExactTerminologyEquivalence",
    "ExactUnitEquivalence",
    "GroundingCandidate",
    "GroundingResult",
    "LiftedFact",
    "SemanticDecision",
    "TerminologyEquivalenceProvider",
    "UnitEquivalenceProvider",
    "classify_graph",
    "ground_graph",
    "ground_source_fact",
    "identifiers_equivalent",
    "instants_equivalent",
    "score_candidate",
]
