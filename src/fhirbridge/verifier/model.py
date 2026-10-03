"""Core data models for independent semantic verification.

Lifters produce :class:`LiftedFact` objects. They describe what a target artifact
contains and where it came from in that artifact, but they do not decide whether
the fact is correct. Correctness is assigned later by the semantic verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LiftedFact:
    """One semantic fact reconstructed from a target artifact."""

    lifted_fact_id: str
    fact_type: str
    subject_ref: str | None
    semantic_payload: dict[str, Any]
    target_paths: tuple[str, ...]
    relationships: tuple[tuple[str, str], ...] = ()
    parser_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundingCandidate:
    """A candidate source-to-target semantic grounding edge."""

    source_fact_id: str
    target_fact_id: str
    score: int
    matched_keys: tuple[str, ...]
    conflicting_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundingResult:
    """Result of independent source-to-target grounding."""

    source_fact_id: str
    target_fact_id: str | None
    status: str
    rationale_code: str
    candidates: tuple[GroundingCandidate, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        allowed = {"grounded", "ambiguous", "unmatched"}
        if self.status not in allowed:
            raise ValueError(f"unsupported grounding status: {self.status}")
