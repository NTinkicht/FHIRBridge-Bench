"""Canonical fact-graph generation utilities.

Canonical scenarios are authored independently of FHIR and HL7 v2 renderers.
"""

from .lab import generate_lab_scenario

__all__ = ["generate_lab_scenario"]
