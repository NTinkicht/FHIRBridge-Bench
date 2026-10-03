"""Canonical fact-graph and benchmark-manifest generation utilities.

Canonical scenarios are authored independently of FHIR and HL7 v2 renderers.
"""

from .lab import generate_lab_scenario
from .manifest import PartitionPlan, build_lab_manifest

__all__ = ["PartitionPlan", "build_lab_manifest", "generate_lab_scenario"]
