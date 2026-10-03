"""Seeded semantic-fault operators for verifier qualification.

Fault generation is intentionally independent of verifier decision logic. These
operators mutate canonical graphs in controlled ways and return mutation
metadata describing what was inserted. The verifier must detect the effects
without importing this module.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class SeededFault:
    fault_id: str
    expected_class: str
    expected_severity: str
    affected_fact_ids: tuple[str, ...]
    mutation: dict[str, Any]


@dataclass(frozen=True)
class MutatedGraph:
    graph: dict[str, Any]
    fault: SeededFault


def _observations(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [fact for fact in graph["facts"] if fact.get("fact_type") == "observation"]


def _patient(graph: dict[str, Any]) -> dict[str, Any]:
    return next(fact for fact in graph["facts"] if fact.get("fact_type") == "patient_identity")


def corrupt_numeric_value(
    graph: dict[str, Any],
    *,
    delta: float = 10.0,
) -> MutatedGraph:
    """F002: alter a grounded numeric result while preserving syntax/context."""

    mutated = deepcopy(graph)
    observation = next(
        fact for fact in _observations(mutated) if isinstance(fact.get("value"), (int, float))
    )
    original = observation["value"]
    observation["value"] = original + delta
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F002",
            expected_class="CORRUPTION",
            expected_severity="S3",
            affected_fact_ids=(observation["fact_id"],),
            mutation={"field": "value", "before": original, "after": observation["value"]},
        ),
    )


def corrupt_unit_without_conversion(
    graph: dict[str, Any],
    *,
    replacement_unit: str = "mmol/L",
) -> MutatedGraph:
    """F003: change a quantity unit without changing its numeric value."""

    mutated = deepcopy(graph)
    observation = next(fact for fact in _observations(mutated) if fact.get("unit") is not None)
    original = deepcopy(observation["unit"])
    observation["unit"] = {
        "system": "http://unitsofmeasure.org",
        "code": replacement_unit,
        "display": replacement_unit,
    }
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F003",
            expected_class="CORRUPTION",
            expected_severity="S3",
            affected_fact_ids=(observation["fact_id"],),
            mutation={"field": "unit", "before": original, "after": deepcopy(observation["unit"])},
        ),
    )


def corrupt_observation_code(
    graph: dict[str, Any],
    *,
    replacement_code: str = "2951-2",
    replacement_display: str = "Sodium [Moles/volume] in Serum or Plasma",
) -> MutatedGraph:
    """F004: replace an observation code with a non-equivalent concept."""

    mutated = deepcopy(graph)
    observation = _observations(mutated)[0]
    original = deepcopy(observation["concept"])
    observation["concept"] = {
        "system": "http://loinc.org",
        "code": replacement_code,
        "display": replacement_display,
        "local_code": None,
    }
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F004",
            expected_class="CORRUPTION",
            expected_severity="S2",
            affected_fact_ids=(observation["fact_id"],),
            mutation={
                "field": "concept",
                "before": original,
                "after": deepcopy(observation["concept"]),
            },
        ),
    )


def corrupt_patient_identifier(
    graph: dict[str, Any],
    *,
    replacement: str = "MRN-WRONG",
) -> MutatedGraph:
    """F005: alter the patient identifier while preserving its namespace."""

    mutated = deepcopy(graph)
    patient = _patient(mutated)
    identifier = patient["identifiers"][0]
    original = identifier["value"]
    identifier["value"] = replacement
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F005",
            expected_class="CORRUPTION",
            expected_severity="S3",
            affected_fact_ids=(patient["fact_id"],),
            mutation={"field": "identifier.value", "before": original, "after": replacement},
        ),
    )


def omit_required_observation(graph: dict[str, Any]) -> MutatedGraph:
    """F008: remove one observation and its direct graph relationships."""

    mutated = deepcopy(graph)
    observation = _observations(mutated)[0]
    fact_id = observation["fact_id"]
    mutated["facts"] = [fact for fact in mutated["facts"] if fact.get("fact_id") != fact_id]

    for fact in mutated["facts"]:
        relations = fact.get("relations")
        if isinstance(relations, list):
            fact["relations"] = [
                relation
                for relation in relations
                if relation.get("target_fact_id") != fact_id
            ]

    mutated["assertions"] = [
        assertion
        for assertion in mutated.get("assertions", [])
        if fact_id not in assertion.get("fact_refs", [])
    ]

    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F008",
            expected_class="OMISSION",
            expected_severity="S3",
            affected_fact_ids=(fact_id,),
            mutation={"operation": "remove_fact", "fact_id": fact_id},
        ),
    )


def shift_observation_time(
    graph: dict[str, Any],
    *,
    minutes: int = 60,
) -> MutatedGraph:
    """F010: shift one observation time while retaining valid ISO syntax."""

    mutated = deepcopy(graph)
    observation = _observations(mutated)[0]
    original = observation["temporal"]["effective_start"]
    parsed = datetime.fromisoformat(original.replace("Z", "+00:00"))
    shifted = parsed + timedelta(minutes=minutes)
    observation["temporal"]["effective_start"] = shifted.isoformat(timespec="seconds")
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F010",
            expected_class="CORRUPTION",
            expected_severity="S2",
            affected_fact_ids=(observation["fact_id"],),
            mutation={
                "field": "temporal.effective_start",
                "before": original,
                "after": observation["temporal"]["effective_start"],
            },
        ),
    )


def fabricate_observation(graph: dict[str, Any]) -> MutatedGraph:
    """F001: add an unsupported but structurally plausible observation fact."""

    mutated = deepcopy(graph)
    source = _observations(mutated)[0]
    fabricated = deepcopy(source)
    fabricated_id = f"{source['fact_id']}-fabricated"
    fabricated["fact_id"] = fabricated_id
    fabricated["concept"] = {
        "system": "urn:fhirbridge:synthetic:fault",
        "code": "UNSUPPORTED-001",
        "display": "Unsupported synthetic analyte",
        "local_code": None,
    }
    fabricated["value"] = 999
    fabricated["provenance"] = deepcopy(source["provenance"])
    mutated["facts"].append(fabricated)

    report = next(fact for fact in mutated["facts"] if fact.get("fact_type") == "diagnostic_report")
    report["relations"].append(
        {"relation_type": "has_result", "target_fact_id": fabricated_id}
    )

    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F001",
            expected_class="FABRICATION",
            expected_severity="S2",
            affected_fact_ids=(fabricated_id,),
            mutation={"operation": "add_fact", "fact_id": fabricated_id},
        ),
    )
