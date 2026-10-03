"""Standard-independent semantic verification utilities."""

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
    "EquivalenceResult",
    "ExactTerminologyEquivalence",
    "ExactUnitEquivalence",
    "GroundingCandidate",
    "GroundingResult",
    "LiftedFact",
    "TerminologyEquivalenceProvider",
    "UnitEquivalenceProvider",
    "ground_graph",
    "ground_source_fact",
    "identifiers_equivalent",
    "instants_equivalent",
    "score_candidate",
]
