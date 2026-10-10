"""Deterministic canonical laboratory scenario generation.

The generator produces standard-independent clinical fact graphs. It must not
contain FHIR paths, HL7 v2 field positions, or reverse-mapping logic.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from random import Random
from typing import Any

_GENERATOR_VERSION = "0.3.0"

_TEMPLATE_RULES = {
    "LAB-001": {
        "label": "single_numeric_normal",
        "mode": "numeric",
        "status": "final",
        "band": "normal",
    },
    "LAB-002": {
        "label": "single_numeric_high",
        "mode": "numeric",
        "status": "final",
        "band": "high",
    },
    "LAB-003": {
        "label": "single_numeric_low",
        "mode": "numeric",
        "status": "final",
        "band": "low",
    },
    "LAB-004": {
        "label": "coded_qualitative_result",
        "mode": "coded",
        "status": "final",
        "band": "normal",
    },
    "LAB-005": {
        "label": "simple_panel",
        "mode": "panel",
        "status": "final",
        "band": "normal",
    },
    "LAB-006": {
        "label": "specimen_linked_result",
        "mode": "numeric",
        "status": "final",
        "band": "normal",
        "specimen_required": True,
    },
    "LAB-007": {
        "label": "preliminary_report",
        "mode": "numeric",
        "status": "preliminary",
        "band": "normal",
    },
    "LAB-008": {
        "label": "corrected_report",
        "mode": "numeric",
        "status": "corrected",
        "band": "normal",
    },
    "LAB-009": {
        "label": "timezone_normalization",
        "mode": "numeric",
        "status": "final",
        "band": "normal",
        "vary_timezone": True,
    },
    "LAB-010": {
        "label": "identifier_namespace_preservation",
        "mode": "numeric",
        "status": "final",
        "band": "normal",
        "multiple_namespaces": True,
    },
    "LAB-011": {
        "label": "repeated_observations_same_code",
        "mode": "repeated",
        "status": "final",
        "band": "normal",
    },
    "LAB-012": {
        "label": "component_topology_ambiguity",
        "mode": "component",
        "status": "final",
        "band": "normal",
        "primary_endpoint_eligible": False,
        "contract_state": "INDETERMINATE",
    },
}

_ANALYTES = (
    {
        "slug": "glucose",
        "code": "2345-7",
        "display": "Glucose [Mass/volume] in Serum or Plasma",
        "unit": "mg/dL",
        "low": 70,
        "high": 99,
        "normal_min": 75,
        "normal_max": 98,
        "high_min": 110,
        "high_max": 180,
        "low_min": 40,
        "low_max": 69,
    },
    {
        "slug": "sodium",
        "code": "2951-2",
        "display": "Sodium [Moles/volume] in Serum or Plasma",
        "unit": "mmol/L",
        "low": 136,
        "high": 145,
        "normal_min": 137,
        "normal_max": 144,
        "high_min": 147,
        "high_max": 160,
        "low_min": 120,
        "low_max": 134,
    },
    {
        "slug": "potassium",
        "code": "2823-3",
        "display": "Potassium [Moles/volume] in Serum or Plasma",
        "unit": "mmol/L",
        "low": 3.5,
        "high": 5.1,
        "normal_min": 3.7,
        "normal_max": 4.9,
        "high_min": 5.3,
        "high_max": 6.2,
        "low_min": 2.7,
        "low_max": 3.3,
    },
)

_EXPECTED_RULE_IDS = [
    "PATIENT_IDENTIFIER_001",
    "PATIENT_NAME_001",
    "PATIENT_BIRTHDATE_001",
    "REPORT_CODE_001",
    "REPORT_EFFECTIVE_TIME_001",
    "REPORT_ISSUED_TIME_001",
    "REPORT_STATUS_001",
    "OBSERVATION_CODE_001",
    "OBSERVATION_VALUE_001",
    "OBSERVATION_UNIT_001",
    "OBSERVATION_REFERENCE_RANGE_001",
    "OBSERVATION_INTERPRETATION_001",
    "OBSERVATION_STATUS_001",
    "OBSERVATION_EFFECTIVE_TIME_001",
]


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _scaled_value(rng: Random, analyte: dict[str, Any], band: str) -> float | int:
    minimum = analyte[f"{band}_min"]
    maximum = analyte[f"{band}_max"]
    if isinstance(minimum, int) and isinstance(maximum, int):
        return rng.randint(minimum, maximum)
    return round(rng.uniform(float(minimum), float(maximum)), 1)


def _interpretation_for_band(band: str) -> tuple[str, str]:
    return {
        "normal": ("N", "Normal"),
        "high": ("H", "High"),
        "low": ("L", "Low"),
    }[band]


def _provenance(template_id: str) -> dict[str, Any]:
    return {
        "scenario_id": template_id,
        "source_artifact": None,
        "source_path": None,
        "authoring_mode": "scenario_authored",
    }


def _patient_fact(template_id: str, seed: int, rng: Random) -> dict[str, Any]:
    suffix = f"{seed:08d}"
    identifiers = [
        {
            "system": "urn:fhirbridge:mrn:primary",
            "value": f"MRN-{rng.randint(100000, 999999)}",
            "type": "MR",
        }
    ]
    if template_id == "LAB-010":
        identifiers.append(
            {
                "system": "urn:fhirbridge:mrn:secondary",
                "value": f"ALT-{rng.randint(100000, 999999)}",
                "type": "PI",
            }
        )

    return {
        "fact_id": f"patient-{suffix}",
        "fact_type": "patient_identity",
        "subject_ref": f"patient-{suffix}",
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
        "identifiers": identifiers,
        "relations": [],
        "attributes": {
            "name": {"family": "Synthetic", "given": [f"Patient{seed}"]},
            "birthDate": "1985-04-12",
        },
        "provenance": _provenance(template_id),
    }


def _report_fact(
    template_id: str,
    patient_id: str,
    report_id: str,
    observation_ids: list[str],
    specimen_id: str | None,
    result_time: datetime,
    issued_time: datetime,
    accession: str,
    status: str,
) -> dict[str, Any]:
    relations = [
        {"relation_type": "has_result", "target_fact_id": obs_id}
        for obs_id in observation_ids
    ]
    if specimen_id is not None:
        relations.append({"relation_type": "has_specimen", "target_fact_id": specimen_id})

    return {
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
        "relations": relations,
        "attributes": {"status": status, "category": "laboratory"},
        "provenance": _provenance(template_id),
    }


def _numeric_observation(
    *,
    template_id: str,
    seed: int,
    index: int,
    analyte: dict[str, Any],
    band: str,
    status: str,
    patient_id: str,
    report_id: str,
    specimen_id: str | None,
    effective_time: datetime,
    rng: Random,
) -> dict[str, Any]:
    value = _scaled_value(rng, analyte, band)
    interpretation_code, interpretation_display = _interpretation_for_band(band)
    fact_id = f"obs-{analyte['slug']}-{seed:08d}-{index}"
    relations = [{"relation_type": "belongs_to_report", "target_fact_id": report_id}]
    if specimen_id is not None:
        relations.append({"relation_type": "specimen", "target_fact_id": specimen_id})

    return {
        "fact_id": fact_id,
        "fact_type": "observation",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": {
            "system": "http://loinc.org",
            "code": analyte["code"],
            "display": analyte["display"],
            "local_code": None,
        },
        "value": value,
        "unit": {
            "system": "http://unitsofmeasure.org",
            "code": analyte["unit"],
            "display": analyte["unit"],
        },
        "temporal": {
            "effective_start": _iso(effective_time),
            "effective_end": None,
            "recorded_at": None,
            "precision": "second",
        },
        "identifiers": [],
        "relations": relations,
        "attributes": {
            "status": status,
            "reference_range": {
                "low": analyte["low"],
                "high": analyte["high"],
                "unit": analyte["unit"],
            },
            "interpretation": {
                "code": interpretation_code,
                "display": interpretation_display,
            },
        },
        "provenance": _provenance(template_id),
    }


def _coded_observation(
    *,
    template_id: str,
    seed: int,
    patient_id: str,
    report_id: str,
    specimen_id: str | None,
    effective_time: datetime,
) -> dict[str, Any]:
    fact_id = f"obs-qualitative-{seed:08d}-0"
    relations = [{"relation_type": "belongs_to_report", "target_fact_id": report_id}]
    if specimen_id is not None:
        relations.append({"relation_type": "specimen", "target_fact_id": specimen_id})

    return {
        "fact_id": fact_id,
        "fact_type": "observation",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": {
            "system": "urn:fhirbridge:synthetic:lab",
            "code": "QUAL-001",
            "display": "Synthetic qualitative laboratory analyte",
            "local_code": None,
        },
        "value": "negative",
        "unit": None,
        "temporal": {
            "effective_start": _iso(effective_time),
            "effective_end": None,
            "recorded_at": None,
            "precision": "second",
        },
        "identifiers": [],
        "relations": relations,
        "attributes": {
            "status": "final",
            "value_code": {
                "system": "urn:fhirbridge:synthetic:result",
                "code": "NEG",
                "display": "Negative",
            },
        },
        "provenance": _provenance(template_id),
    }


def _component_observation(
    *,
    template_id: str,
    seed: int,
    patient_id: str,
    report_id: str,
    effective_time: datetime,
) -> dict[str, Any]:
    return {
        "fact_id": f"obs-component-{seed:08d}-0",
        "fact_type": "observation",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": {
            "system": "urn:fhirbridge:synthetic:lab",
            "code": "COMP-001",
            "display": "Synthetic component-bearing laboratory observation",
            "local_code": None,
        },
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": _iso(effective_time),
            "effective_end": None,
            "recorded_at": None,
            "precision": "second",
        },
        "identifiers": [],
        "relations": [
            {"relation_type": "belongs_to_report", "target_fact_id": report_id}
        ],
        "attributes": {
            "status": "final",
            "components": [
                {"code": "A", "value": 1.2, "unit": "arb"},
                {"code": "B", "value": 3.4, "unit": "arb"},
            ],
            "contract_state": "INDETERMINATE",
        },
        "provenance": _provenance(template_id),
    }


def _specimen_fact(
    template_id: str,
    seed: int,
    patient_id: str,
    observation_ids: list[str],
    specimen_time: datetime,
    identifier: str,
) -> dict[str, Any]:
    return {
        "fact_id": f"specimen-{seed:08d}",
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
                "value": identifier,
                "type": "specimen",
            }
        ],
        "relations": [
            {"relation_type": "specimen_for_observation", "target_fact_id": obs_id}
            for obs_id in observation_ids
        ],
        "attributes": {
            "type_label": "serum_or_plasma",
            "collection_method_label": "venipuncture",
        },
        "provenance": _provenance(template_id),
    }


def _order_fact(
    template_id: str,
    seed: int,
    patient_id: str,
    report_id: str,
    authored_time: datetime,
    rng: Random,
) -> dict[str, Any]:
    """Author one standard-independent laboratory order context fact."""

    return {
        "fact_id": f"order-{seed:08d}",
        "fact_type": "order",
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
            "effective_start": None,
            "effective_end": None,
            "recorded_at": _iso(authored_time),
            "precision": "second",
        },
        "identifiers": [
            {
                "system": "urn:fhirbridge:lab-order",
                "value": f"ORD-{rng.randint(100000, 999999)}",
                "type": "order",
            }
        ],
        "relations": [
            {"relation_type": "has_report", "target_fact_id": report_id}
        ],
        "attributes": {
            "lifecycle_status": "completed",
            "request_intent": "order",
            "requester": {
                "identifiers": [
                    {
                        "system": "urn:fhirbridge:provider",
                        "value": f"PROV-{seed:08d}",
                        "type": "provider",
                    }
                ],
                "display": f"Synthetic Ordering Provider {seed}",
            },
        },
        "provenance": _provenance(template_id),
    }


def generate_lab_scenario(
    template_id: str,
    seed: int,
    *,
    implementation_variant_id: str = "canonical_profile",
    include_specimen: bool | None = None,
    partition: str = "development",
    include_order_context: bool = False,
) -> dict[str, Any]:
    """Generate one deterministic canonical lab fact graph.

    Standard-specific renderers are intentionally separate research components.
    ``partition`` is metadata only; partition assignment itself should be frozen
    through the benchmark manifest before confirmatory inference.
    """

    try:
        template = _TEMPLATE_RULES[template_id]
    except KeyError as exc:
        supported = ", ".join(sorted(_TEMPLATE_RULES))
        message = f"unsupported template {template_id!r}; choose one of {supported}"
        raise ValueError(message) from exc

    if partition not in {"development", "pilot", "confirmatory", "external"}:
        raise ValueError(f"unsupported partition: {partition}")

    rng = Random(seed)
    suffix = f"{seed:08d}"
    patient_id = f"patient-{suffix}"
    report_id = f"report-{suffix}"
    specimen_id = f"specimen-{suffix}"

    specimen_required = bool(template.get("specimen_required"))
    if include_specimen is None:
        include_specimen = specimen_required or template_id in {"LAB-005", "LAB-010"}
    if specimen_required and not include_specimen:
        raise ValueError(f"{template_id} requires specimen context")

    offset_hours = rng.choice([-5, 0, 4, 8]) if template.get("vary_timezone") else 4
    tz = timezone(timedelta(hours=offset_hours))
    base = datetime(2026, 1, 1, 8, 0, tzinfo=tz) + timedelta(
        days=rng.randint(0, 250),
        minutes=rng.randint(0, 240),
    )
    specimen_time = base
    result_time = base + timedelta(minutes=rng.randint(5, 25))
    issued_time = result_time + timedelta(minutes=rng.randint(10, 45))
    order_authored_time = base - timedelta(hours=2)

    patient = _patient_fact(template_id, seed, rng)
    mode = template["mode"]
    observations: list[dict[str, Any]] = []
    specimen_ref = specimen_id if include_specimen else None

    if mode == "coded":
        observations.append(
            _coded_observation(
                template_id=template_id,
                seed=seed,
                patient_id=patient_id,
                report_id=report_id,
                specimen_id=specimen_ref,
                effective_time=result_time,
            )
        )
    elif mode == "panel":
        for index, analyte in enumerate(_ANALYTES):
            observations.append(
                _numeric_observation(
                    template_id=template_id,
                    seed=seed,
                    index=index,
                    analyte=analyte,
                    band="normal",
                    status=template["status"],
                    patient_id=patient_id,
                    report_id=report_id,
                    specimen_id=specimen_ref,
                    effective_time=result_time,
                    rng=rng,
                )
            )
    elif mode == "repeated":
        analyte = _ANALYTES[0]
        for index in range(2):
            observations.append(
                _numeric_observation(
                    template_id=template_id,
                    seed=seed,
                    index=index,
                    analyte=analyte,
                    band="normal",
                    status=template["status"],
                    patient_id=patient_id,
                    report_id=report_id,
                    specimen_id=specimen_ref,
                    effective_time=result_time + timedelta(minutes=index * 60),
                    rng=rng,
                )
            )
    elif mode == "component":
        observations.append(
            _component_observation(
                template_id=template_id,
                seed=seed,
                patient_id=patient_id,
                report_id=report_id,
                effective_time=result_time,
            )
        )
    else:
        observations.append(
            _numeric_observation(
                template_id=template_id,
                seed=seed,
                index=0,
                analyte=_ANALYTES[0],
                band=template["band"],
                status=template["status"],
                patient_id=patient_id,
                report_id=report_id,
                specimen_id=specimen_ref,
                effective_time=result_time,
                rng=rng,
            )
        )

    observation_ids = [observation["fact_id"] for observation in observations]
    report = _report_fact(
        template_id,
        patient_id,
        report_id,
        observation_ids,
        specimen_ref,
        result_time,
        issued_time,
        f"ACC-{rng.randint(100000, 999999)}",
        template["status"],
    )

    order: dict[str, Any] | None = None
    if include_order_context:
        order = _order_fact(
            template_id,
            seed,
            patient_id,
            report_id,
            order_authored_time,
            rng,
        )
        report["relations"].append(
            {
                "relation_type": "based_on_order",
                "target_fact_id": order["fact_id"],
            }
        )

    facts = [patient]
    if order is not None:
        facts.append(order)
    facts.extend([report, *observations])
    specimen: dict[str, Any] | None = None
    if include_specimen:
        specimen = _specimen_fact(
            template_id,
            seed,
            patient_id,
            observation_ids,
            specimen_time,
            f"SPM-{rng.randint(100000, 999999)}",
        )
        facts.append(specimen)

    assertions = [
        {
            "assertion_id": f"A-{suffix}-SUBJECT",
            "assertion_type": "same_subject",
            "fact_refs": [fact["fact_id"] for fact in facts],
            "parameters": {},
        },
        {
            "assertion_id": f"A-{suffix}-STATUS",
            "assertion_type": "status_consistency",
            "fact_refs": [report_id, *observation_ids],
            "parameters": {
                "report_status": template["status"],
                "observation_status": template["status"],
            },
        },
    ]
    if order is not None:
        assertions.append(
            {
                "assertion_id": f"A-{suffix}-ORDER-REPORT",
                "assertion_type": "belongs_to_order",
                "fact_refs": [report_id, order["fact_id"]],
                "parameters": {},
            }
        )

    for observation in observations:
        assertions.append(
            {
                "assertion_id": f"A-{suffix}-{observation['fact_id']}-REPORT",
                "assertion_type": "belongs_to_report",
                "fact_refs": [observation["fact_id"], report_id],
                "parameters": {},
            }
        )
        if observation["unit"] is not None:
            assertions.append(
                {
                    "assertion_id": f"A-{suffix}-{observation['fact_id']}-VALUEUNIT",
                    "assertion_type": "value_unit_pair",
                    "fact_refs": [observation["fact_id"]],
                    "parameters": {
                        "expected_value": observation["value"],
                        "expected_unit": observation["unit"]["code"],
                    },
                }
            )
    if specimen is not None:
        for observation_id in observation_ids:
            assertions.append(
                {
                    "assertion_id": f"A-{suffix}-{observation_id}-SPECIMEN",
                    "assertion_type": "specimen_for_observation",
                    "fact_refs": [specimen_id, observation_id],
                    "parameters": {},
                }
            )

    expected_rule_ids = list(_EXPECTED_RULE_IDS)
    if include_order_context:
        expected_rule_ids.extend(
            [
                "ORDER_IDENTIFIER_MAPPING_001",
                "ORDER_REQUESTER_MAPPING_001",
                "ORDER_CODE_MAPPING_001",
                "REPORT_BASEDON_ORDER_001",
            ]
        )
    if include_specimen:
        expected_rule_ids.extend(
            [
                "SPECIMEN_IDENTIFIER_001",
                "SPECIMEN_TYPE_001",
                "SPECIMEN_COLLECTION_TIME_001",
            ]
        )

    primary_endpoint_eligible = bool(template.get("primary_endpoint_eligible", True))
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
            "partition": partition,
            "primary_endpoint_eligible": primary_endpoint_eligible,
            "contract_state": template.get("contract_state", "SCORABLE"),
            "expected_rule_ids": expected_rule_ids,
            "notes": "Generated from canonical semantics before standard-specific rendering.",
        },
    }
    return deepcopy(graph)
