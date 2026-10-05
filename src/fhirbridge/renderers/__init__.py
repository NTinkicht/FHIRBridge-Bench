"""Clean-room reference renderer interfaces and development implementations.

Concrete renderer implementations must remain semantically independent.
"""

from .base import CanonicalRenderer, RenderManifest, RenderResult, RenderWarning
from .fhir_r4_a import FhirR4LabRendererA

__all__ = [
    "CanonicalRenderer",
    "FhirR4LabRendererA",
    "RenderManifest",
    "RenderResult",
    "RenderWarning",
]
