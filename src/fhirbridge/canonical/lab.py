"""Deterministic canonical laboratory scenario generation.

The generator produces standard-independent clinical fact graphs. It must not
contain FHIR paths, HL7 v2 field positions, or reverse-mapping logic.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from random import Random
from typing import Any

_GENERATOR_VERSION = "0.1.0"

_TEMPLATE_RULES = {
    "LAB-001": {"label": "single_numeric_normal", "status": "final", "band": "normal"},
    "LAB-002": {"label": "single_numeric_high", "status": "final", "band": "high"},
    "LAB-003": {"label": "single_numeric_low", "status": "final", "band": "low"},
    "LAB-007": {"label": "preliminary_report", "status": "preliminary", "band": "normal"},
    "LAB-008": {"label": "corrected_report", "status": "corrected", "band": "normal"},
}


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _value_for_band(rng: Random, band: str) -> tuple[int, str]:
    if band == "normal":
        return rng.randint(75, 98), "N"
    if band == "high":
        return rng.randint(110, 180), "H"
    if band == "low":
        return rng.randint(40, 69), "L"
    raise ValueError(f"unsupported result band: {band}")


def generate_lab_scenario(
    template_id: str,
    seed: int,
    *,
    implementation_variant_id: str = "canonical_profile",
    include_specimen: bool = True,
) -> dict[str, Any]:
    """Generate a deterministic canonical lab fact graph.

    Only canonical semantics are generated here. Standard-specific renderers are
    intentionally separate research components.
    """

    try:
        template = _TEMPLATE_RULES[template_id]
    except KeyError as exc:
        supported = ", ".join(sorted(_TEMPLATE_RULES))
        message = f"unsupported template {template_id!r}; choose one of {supported}"
        raise ValueError(message) from exc

    rng = Random(seed)
    suffix = f"{seed:08d}"
    patient_id = f"patient-{suffix}"
    report_id = f"report-{suffix}"
    observation_id = f"obs-glucose-{suffix}"
    specimen_id = f"specimen-{suffix}"

    tz = timezone(timedelta(hours=4))
    base = datetime(2026, 1, 1, 8, 0, tzinfo=tz) + timedelta(
        days=rng.randint(0, 250),
        minutes=rng.randint(0, 240),
    )
    specimen_time = base
    result_time = base + timedelta(minutes=rng.randint(5, 25))
    issued_time = result_time + timedelta(minutes=rng.randint(10, 45))

    value, interpretation = _value_for_band(rng, template["band"])
    mrn = f"MRN-{rng.randint(100000, 999999)}"
    accession = f"ACC-{rng.randint(100000, 999999)}"
    specimen_identifier = f"SPM-{rng.randint(100000, 999999)}"

    facts: list[dict[str, Any]] = [
        {
            "fact_id": patient_id,
            "fact_type": "patient_identity",
            "subject_ref": patient_id,
            "encounter_ref": None,
            "concept": None,
            "value": None,
            "unit": None,
            "temporal": {
                "effective_start": "1985-04-12",
                "effective_end": None,
                "recorded_at": None,
                "precision": "day",
            },
            "identifiers": [
                {
                    "system": "urn:fhirbridge:mrn",
                    "value": mrn,
                    "type": "MR",
                }
            ],
            "relations": [],
            "attributes": {
                "name": {"family": "Synthetic", "given": [f"Patient{seed}"]},
                "birthDate": "1985-04-12",
            },
            "provenance": {
                "scenario_id": template_id,
                "source_artifact": None,
                "source_path": None,
                "authoring_mode": "scenario_authored",
            },
        },
        {
            "fact_id": report_id,
            "fact_type": "diagnostic_report",
            "subject_ref": patient_id,
            "encounter_ref": None,
            "concept": {
                "system": "http://loinc.org",
                "code": "24323-8",
                "display": "Comprehensive metabolic panel",
                "local_code": None,
            },
            "value": None,
            "unit": None,
            "temporal": {
                "effective_start": _iso(result_time),
                "effective_end": None,
                "recorded_at": _iso(issued_time),
                "precision": "second",
            },
            "identifiers": [
                {
                    "system": "urn:fhirbridge:accession",
                    "value": accession,
                    "type": "accession",
                }
            ],
            "relations": [
                {"relation_type": "has_result", "target_fact_id": observation_id}
            ],
            "attributes": {
                "status": template["status"],
                "category": "laboratory",
            },
            "provenance": {
                "scenario_id": template_id,
                "source_artifact": None,
                "source_path": None,
                "authoring_mode": "scenario_authored",
            },
        },
        {
            "fact_id": observation_id,
            "fact_type": "observation",
            "subject_ref": patient_id,
            "encounter_ref": None,
            "concept": {
                "system": "http://loinc.org",
                "code": "2345-7",
                "display": "Glucose [Mass/volume] in Serum or Plasma",
                "local_code": None,
            },
            "value": value,
            "unit": {
                "system": "http://unitsofmeasure.org",
                "code": "mg/dL",
                "display": "mg/dL",
            },
            "temporal": {
                "effective_start": _iso(result_time),
                "effective_end": None,
                "recorded_at": None,
                "precision": "second",
            },
            "identifiers": [],
            "relations": [
                {"relation_type": "belongs_to_report", "target_fact_id": report_id}
            ],
            "attributes": {
                "status": template["status"],
                "reference_range": {"low": 70, "high": 99, "unit": "mg/dL"},
                "interpretation": {
                    "code": interpretation,
                    "display": {"N": "Normal", "H": "High", "L": "Low"}[interpretation],
                },
            },
            "provenance": {
                "scenario_id": template_id,
                "source_artifact": None,
                "source_path": None,
                "authoring_mode": "scenario_authored",
            },
        },
    ]

    if include_specimen:
        facts[1]["relations"].append(
            {"relation_type": "has_specimen", "target_fact_id": specimen_id}
        )
        facts[2]["relations"].append(
            {"relation_type": "specimen", "target_fact_id": specimen_id}
        )
        facts.append(
            {
                "fact_id": specimen_id,
                "fact_type": "specimen",
                "subject_ref": patient_id,
                "encounter_ref": None,
                "concept": None,
                "value": None,
                "unit": None,
                "temporal": {
                    "effective_start": _iso(specimen_time),
                    "effective_end": None,
                    "recorded_at": None,
                    "precision": "second",
                },
                "identifiers": [
                    {
                        "system": "urn:fhirbridge:specimen",
                        "value": specimen_identifier,
                        "type": "specimen",
                    }
                ],
                "relations": [
                    {
                        "relation_type": "specimen_for_observation",
                        "target_fact_id": observation_id,
                    }
                ],
                "attributes": {
                    "type_label": "serum_or_plasma",
                    "collection_method_label": "venipuncture",
                },
                "provenance": {
                    "scenario_id": template_id,
                    "source_artifact": None,
                    "source_path": None,
                    "authoring_mode": "scenario_authored",
                },
            }
        )

    assertions = [
        {
            "assertion_id": f"A-{suffix}-SUBJECT",
            "assertion_type": "same_subject",
            "fact_refs": [fact["fact_id"] for fact in facts],
            "parameters": {},
        },
        {
            "assertion_id": f"A-{suffix}-REPORT",
            "assertion_type": "belongs_to_report",
            "fact_refs": [observation_id, report_id],
            "parameters": {},
        },
        {
            "assertion_id": f"A-{suffix}-VALUEUNIT",
            "assertion_type": "value_unit_pair",
            "fact_refs": [observation_id],
            "parameters": {"expected_value": value, "expected_unit": "mg/dL"},
        },
        {
            "assertion_id": f"A-{suffix}-STATUS",
            "assertion_type": "status_consistency",
            "fact_refs": [report_id, observation_id],
            "parameters": {
                "report_status": template["status"],
                "observation_status": template["status"],
            },
        },
    ]

    if include_specimen:
        assertions.append(
            {
                "assertion_id": f"A-{suffix}-SPECIMEN",
                "assertion_type": "specimen_for_observation",
                "fact_refs": [specimen_id, observation_id],
                "parameters": {},
            }
        )

    graph = {
        "graph_id": f"{template_id}-{suffix}",
        "schema_version": "0.1.0",
        "scenario_type": "laboratory_result",
        "patient_ref": patient_id,
        "encounter_ref": None,
        "facts": facts,
        "assertions": assertions,
        "scenario_metadata": {
            "seed": seed,
            "generator_version": _GENERATOR_VERSION,
            "clinical_template": template["label"],
            "implementation_variant_id": implementation_variant_id,
            "synthetic_only": True,
            "notes": "Generated from canonical semantics before standard-specific rendering.",
        },
    }
    return deepcopy(graph)
