"""Shared non-semantic interfaces for clean-room reference renderers.

This module defines the shape of renderer inputs/outputs only. It intentionally
contains no fact-to-FHIR or fact-to-HL7 v2 mapping logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RenderWarning:
    """One non-fatal renderer warning."""

    code: str
    message: str
    fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderManifest:
    """Audit sidecar for one rendered artifact.

    The manifest is never accepted by the verifier as proof that a mapping is
    semantically correct.
    """

    graph_id: str
    renderer_id: str
    renderer_version: str
    contract_id: str
    contract_version: str
    target_standard: str
    target_profile: str
    structural_validation_ref: str | None = None
    warnings: tuple[RenderWarning, ...] = ()
    declared_loss_fact_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderResult:
    """Rendered standards artifact plus its non-authoritative audit manifest."""

    media_type: str
    artifact: str | dict[str, Any]
    manifest: RenderManifest


@runtime_checkable
class CanonicalRenderer(Protocol):
    """Minimal protocol all clean-room reference renderers must implement."""

    @property
    def renderer_id(self) -> str:
        """Stable renderer identifier."""
        ...

    @property
    def renderer_version(self) -> str:
        """Version pinned in benchmark run manifests."""
        ...

    def render(
        self,
        graph: dict[str, Any],
        *,
        contract: dict[str, Any],
    ) -> RenderResult:
        """Render one canonical graph under an explicit projectability contract."""
        ...
