"""Composed seeded semantic faults for verifier qualification.

Multi-fault generation remains independent of verifier decision logic. The
functions in this module compose existing single-fault operators and preserve
component metadata so qualification can test precedence and co-occurring error
behavior without teaching the verifier how the faults were constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .faults import (
    MutatedGraph,
    SeededFault,
    corrupt_numeric_value,
    corrupt_unit_without_conversion,
    fabricate_observation,
    misattribute_result_to_patient,
    omit_required_observation,
)


@dataclass(frozen=True)
class MultiFault:
    fault_id: str
    name: str
    components: tuple[SeededFault, ...]
    expected_resolution: tuple[str, ...]
    affected_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class MultiMutatedGraph:
    graph: dict[str, Any]
    fault: MultiFault


def _affected(components: tuple[SeededFault, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            fact_id
            for component in components
            for fact_id in component.affected_fact_ids
        )
    )


def value_plus_unit_joint_corruption(
    graph: dict[str, Any],
    *,
    value_delta: float = 10.0,
    replacement_unit: str = "mmol/L",
) -> MultiMutatedGraph:
    """MF001: jointly corrupt value and unit on a grounded numeric result."""

    value_mutant: MutatedGraph = corrupt_numeric_value(graph, delta=value_delta)
    unit_mutant: MutatedGraph = corrupt_unit_without_conversion(
        value_mutant.graph,
        replacement_unit=replacement_unit,
    )
    components = (value_mutant.fault, unit_mutant.fault)
    return MultiMutatedGraph(
        graph=unit_mutant.graph,
        fault=MultiFault(
            fault_id="MF001",
            name="value_plus_unit_joint_corruption",
            components=components,
            expected_resolution=("CORRUPTION",),
            affected_fact_ids=_affected(components),
        ),
    )


def patient_swap_plus_valid_result(
    graph: dict[str, Any],
    *,
    foreign_subject_ref: str = "patient-foreign-target",
) -> MultiMutatedGraph:
    """MF002: preserve result semantics but attach the result to another patient."""

    mutant = misattribute_result_to_patient(
        graph,
        foreign_subject_ref=foreign_subject_ref,
    )
    components = (mutant.fault,)
    return MultiMutatedGraph(
        graph=mutant.graph,
        fault=MultiFault(
            fault_id="MF002",
            name="patient_swap_plus_valid_result",
            components=components,
            expected_resolution=("MISATTRIBUTION",),
            affected_fact_ids=_affected(components),
        ),
    )


def omission_plus_fabricated_replacement(graph: dict[str, Any]) -> MultiMutatedGraph:
    """MF003: remove one required result and add an unrelated replacement."""

    omission = omit_required_observation(graph)
    fabricated = fabricate_observation(omission.graph)
    components = (omission.fault, fabricated.fault)
    return MultiMutatedGraph(
        graph=fabricated.graph,
        fault=MultiFault(
            fault_id="MF003",
            name="omitted_required_result_plus_fabricated_replacement",
            components=components,
            expected_resolution=("OMISSION", "FABRICATION"),
            affected_fact_ids=_affected(components),
        ),
    )
