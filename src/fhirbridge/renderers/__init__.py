"""Clean-room reference renderer interfaces.

Concrete renderer implementations must remain semantically independent.
"""

from .base import CanonicalRenderer, RenderManifest, RenderResult, RenderWarning

__all__ = ["CanonicalRenderer", "RenderManifest", "RenderResult", "RenderWarning"]
