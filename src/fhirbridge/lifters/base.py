"""Shared non-semantic interfaces for independent target lifters.

A lifter reconstructs candidate canonical facts from one concrete standards
artifact. It must not decide whether those facts are correct and must not import
semantic mapping code from any reference renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from fhirbridge.verifier.model import LiftedFact


@dataclass(frozen=True)
class LiftWarning:
    """One non-fatal parsing/lifting warning."""

    code: str
    message: str
    target_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiftResult:
    """Canonical facts reconstructed from one target artifact."""

    artifact_id: str
    lifter_id: str
    lifter_version: str
    source_standard: str
    source_profile: str
    facts: tuple[LiftedFact, ...]
    warnings: tuple[LiftWarning, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ArtifactLifter(Protocol):
    """Minimal protocol for independent FHIR and HL7 v2 lifters."""

    @property
    def lifter_id(self) -> str:
        ...

    @property
    def lifter_version(self) -> str:
        ...

    def lift(self, artifact: str | dict[str, Any], *, artifact_id: str) -> LiftResult:
        """Reconstruct semantic facts and evidence paths from a concrete artifact."""
        ...
