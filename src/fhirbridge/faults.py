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


def _report(graph: dict[str, Any]) -> dict[str, Any]:
    return next(fact for fact in graph["facts"] if fact.get("fact_type") == "diagnostic_report")


def _specimen(graph: dict[str, Any]) -> dict[str, Any]:
    return next(fact for fact in graph["facts"] if fact.get("fact_type") == "specimen")


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


def misattribute_result_to_patient(
    graph: dict[str, Any],
    *,
    foreign_subject_ref: str = "patient-foreign-target",
) -> MutatedGraph:
    """F006: attach an otherwise correct result to a wrong patient reference.

    This is a target-side semantic mutant. The foreign reference intentionally
    does not become a new canonical source fact; adding such a fact would turn
    the case into a mixed misattribution-plus-fabrication mutant.
    """

    mutated = deepcopy(graph)
    observation = _observations(mutated)[0]
    original = observation["subject_ref"]
    observation["subject_ref"] = foreign_subject_ref
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F006",
            expected_class="MISATTRIBUTION",
            expected_severity="S3",
            affected_fact_ids=(observation["fact_id"],),
            mutation={
                "field": "subject_ref",
                "before": original,
                "after": foreign_subject_ref,
            },
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


def corrupt_result_status(
    graph: dict[str, Any],
    *,
    replacement_status: str = "preliminary",
) -> MutatedGraph:
    """F011: change a report/result status without source support."""

    mutated = deepcopy(graph)
    observation = _observations(mutated)[0]
    original = observation["attributes"].get("status")
    observation["attributes"]["status"] = replacement_status
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F011",
            expected_class="CORRUPTION",
            expected_severity="S2",
            affected_fact_ids=(observation["fact_id"],),
            mutation={
                "field": "attributes.status",
                "before": original,
                "after": replacement_status,
            },
        ),
    )


def corrupt_interpretation(
    graph: dict[str, Any],
    *,
    replacement_code: str = "H",
    replacement_display: str = "High",
) -> MutatedGraph:
    """F012: replace interpretation semantics while retaining the result value."""

    mutated = deepcopy(graph)
    observation = next(
        fact
        for fact in _observations(mutated)
        if isinstance(fact.get("attributes", {}).get("interpretation"), dict)
    )
    original = deepcopy(observation["attributes"]["interpretation"])
    observation["attributes"]["interpretation"] = {
        "code": replacement_code,
        "display": replacement_display,
    }
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F012",
            expected_class="CORRUPTION",
            expected_severity="S2",
            affected_fact_ids=(observation["fact_id"],),
            mutation={
                "field": "attributes.interpretation",
                "before": original,
                "after": deepcopy(observation["attributes"]["interpretation"]),
            },
        ),
    )


def corrupt_reference_range(
    graph: dict[str, Any],
    *,
    high_delta: float = 25.0,
) -> MutatedGraph:
    """F013: alter one structured reference-range bound."""

    mutated = deepcopy(graph)
    observation = next(
        fact
        for fact in _observations(mutated)
        if isinstance(fact.get("attributes", {}).get("reference_range"), dict)
    )
    reference_range = observation["attributes"]["reference_range"]
    original = deepcopy(reference_range)
    reference_range["high"] = reference_range["high"] + high_delta
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F013",
            expected_class="CORRUPTION",
            expected_severity="S2",
            affected_fact_ids=(observation["fact_id"],),
            mutation={
                "field": "attributes.reference_range.high",
                "before": original,
                "after": deepcopy(reference_range),
            },
        ),
    )


def corrupt_specimen_type(
    graph: dict[str, Any],
    *,
    replacement_type_label: str = "whole_blood",
) -> MutatedGraph:
    """F015: replace specimen type with a non-equivalent semantic type."""

    mutated = deepcopy(graph)
    specimen = _specimen(mutated)
    original = specimen["attributes"].get("type_label")
    specimen["attributes"]["type_label"] = replacement_type_label
    return MutatedGraph(
        graph=mutated,
        fault=SeededFault(
            fault_id="F015",
            expected_class="CORRUPTION",
            expected_severity="S2",
            affected_fact_ids=(specimen["fact_id"],),
            mutation={
                "field": "attributes.type_label",
                "before": original,
                "after": replacement_type_label,
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

    report = _report(mutated)
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
