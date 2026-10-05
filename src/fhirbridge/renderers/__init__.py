"""Clean-room reference renderer interfaces and development implementations.

Concrete renderer implementations must remain semantically independent.
"""

from .base import CanonicalRenderer, RenderManifest, RenderResult, RenderWarning
from .fhir_r4_a import FhirR4LabRendererA
from .hl7v251_oru_a import Hl7V251OruRendererA

__all__ = [
    "CanonicalRenderer",
    "FhirR4LabRendererA",
    "Hl7V251OruRendererA",
    "RenderManifest",
    "RenderResult",
    "RenderWarning",
]
