"""Standard-independent semantic verification utilities."""

from .classifier import ClassificationResult, SemanticDecision
from .contract_classifier import classify_graph
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
from .policy import FactComparisonPolicy, VerificationPolicy, compile_verification_policy

__all__ = [
    "ClassificationResult",
    "EquivalenceResult",
    "ExactTerminologyEquivalence",
    "ExactUnitEquivalence",
    "FactComparisonPolicy",
    "GroundingCandidate",
    "GroundingResult",
    "LiftedFact",
    "SemanticDecision",
    "TerminologyEquivalenceProvider",
    "UnitEquivalenceProvider",
    "VerificationPolicy",
    "classify_graph",
    "compile_verification_policy",
    "ground_graph",
    "ground_source_fact",
    "identifiers_equivalent",
    "instants_equivalent",
    "score_candidate",
]
