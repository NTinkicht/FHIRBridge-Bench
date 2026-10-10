"""Independent FHIR R4 laboratory artifact lifter.

The lifter reconstructs candidate semantic facts from ordinary FHIR R4 JSON. It
must not import Renderer A mapping functions and does not decide whether lifted
facts are faithful. That decision belongs to the verifier.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fhirbridge.verifier.model import LiftedFact

from .base import LiftResult, LiftWarning

_LIFTER_ID = "fhir-r4-lab-lifter"
_LIFTER_VERSION = "0.2.0-dev"


def _local_id(resource_type: str, resource_id: str) -> str:
    return f"fhir::{resource_type}/{resource_id}"


def _reference_id(reference: Any) -> str | None:
    if not isinstance(reference, dict):
        return None
    raw = reference.get("reference")
    if not isinstance(raw, str) or "/" not in raw:
        return None
    resource_type, resource_id = raw.split("/", 1)
    if not resource_type or not resource_id:
        return None
    return _local_id(resource_type, resource_id)


def _first_coding(codeable: Any) -> dict[str, Any] | None:
    if not isinstance(codeable, dict):
        return None
    coding = codeable.get("coding")
    if not isinstance(coding, list) or not coding:
        return None
    first = coding[0]
    return first if isinstance(first, dict) else None


def _concept(codeable: Any) -> dict[str, Any] | None:
    if not isinstance(codeable, dict):
        return None
    coding = _first_coding(codeable)
    if coding is None and codeable.get("text") is None:
        return None
    return {
        "system": coding.get("system") if coding else None,
        "code": coding.get("code") if coding else None,
        "display": (
            coding.get("display")
            if coding and coding.get("display") is not None
            else codeable.get("text")
        ),
        "local_code": None,
    }


def _identifiers(resource: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    identifiers = resource.get("identifier", [])
    if not isinstance(identifiers, list):
        return result
    for identifier in identifiers:
        if not isinstance(identifier, dict) or identifier.get("value") is None:
            continue
        type_text = None
        identifier_type = identifier.get("type")
        if isinstance(identifier_type, dict):
            if identifier_type.get("text") is not None:
                type_text = identifier_type["text"]
            else:
                coding = _first_coding(identifier_type)
                if coding is not None:
                    type_text = coding.get("code")
        result.append(
            {
                "system": identifier.get("system"),
                "value": identifier["value"],
                "type": type_text,
            }
        )
    return result


def _unit_from_quantity(quantity: Any) -> dict[str, Any] | None:
    if not isinstance(quantity, dict):
        return None
    if not any(quantity.get(key) is not None for key in ("unit", "system", "code")):
        return None
    return {
        "system": quantity.get("system"),
        "code": quantity.get("code"),
        "display": quantity.get("unit"),
    }


def _observation_value(
    resource: dict[str, Any],
) -> tuple[Any, dict[str, Any] | None, dict[str, Any]]:
    attributes: dict[str, Any] = {}
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict):
        return quantity.get("value"), _unit_from_quantity(quantity), attributes

    coded = resource.get("valueCodeableConcept")
    if isinstance(coded, dict):
        coding = _first_coding(coded)
        attributes["value_code"] = {
            "system": coding.get("system") if coding else None,
            "code": coding.get("code") if coding else None,
            "display": coding.get("display") if coding else coded.get("text"),
        }
        return coded.get("text"), None, attributes

    if "valueBoolean" in resource:
        return resource.get("valueBoolean"), None, attributes
    if "valueString" in resource:
        return resource.get("valueString"), None, attributes
    return None, None, attributes


def _reference_range(resource: dict[str, Any]) -> dict[str, Any] | None:
    ranges = resource.get("referenceRange")
    if not isinstance(ranges, list) or not ranges or not isinstance(ranges[0], dict):
        return None
    first = ranges[0]
    low = first.get("low") if isinstance(first.get("low"), dict) else {}
    high = first.get("high") if isinstance(first.get("high"), dict) else {}
    unit = low.get("code") or low.get("unit") or high.get("code") or high.get("unit")
    result = {
        "low": low.get("value"),
        "high": high.get("value"),
        "unit": unit,
    }
    if all(value is None for value in result.values()):
        return None
    return result


def _interpretation(resource: dict[str, Any]) -> dict[str, Any] | None:
    items = resource.get("interpretation")
    if not isinstance(items, list) or not items:
        return None
    coding = _first_coding(items[0])
    if coding is None:
        return None
    return {"code": coding.get("code"), "display": coding.get("display")}


def _resource_entries(bundle: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    entries = bundle.get("entry", [])
    if not isinstance(entries, list):
        return []
    result: list[tuple[int, dict[str, Any]]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
            continue
        result.append((index, entry["resource"]))
    return result


def _patient_fact(resource: dict[str, Any], path: str) -> LiftedFact:
    resource_id = str(resource["id"])
    lifted_id = _local_id("Patient", resource_id)
    names = resource.get("name", [])
    name = (
        deepcopy(names[0])
        if isinstance(names, list) and names and isinstance(names[0], dict)
        else None
    )
    birth_date = resource.get("birthDate")
    payload = {
        "fact_type": "patient_identity",
        "subject_ref": lifted_id,
        "encounter_ref": None,
        "concept": None,
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": birth_date,
            "effective_end": None,
            "recorded_at": None,
            "precision": "day" if birth_date is not None else None,
        },
        "identifiers": _identifiers(resource),
        "relations": [],
        "attributes": {"name": name, "birthDate": birth_date},
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="patient_identity",
        subject_ref=lifted_id,
        semantic_payload=payload,
        target_paths=(path,),
    )


def _observation_fact(
    resource: dict[str, Any],
    path: str,
    *,
    observation_report_links: dict[str, list[str]],
) -> LiftedFact:
    resource_id = str(resource["id"])
    lifted_id = _local_id("Observation", resource_id)
    value, unit, value_attributes = _observation_value(resource)
    attributes: dict[str, Any] = {"status": resource.get("status"), **value_attributes}
    reference_range = _reference_range(resource)
    if reference_range is not None:
        attributes["reference_range"] = reference_range
    interpretation = _interpretation(resource)
    if interpretation is not None:
        attributes["interpretation"] = interpretation

    relationships: list[tuple[str, str]] = [
        ("belongs_to_report", report_id)
        for report_id in observation_report_links.get(lifted_id, [])
    ]
    specimen = _reference_id(resource.get("specimen"))
    if specimen is not None:
        relationships.append(("specimen", specimen))

    payload = {
        "fact_type": "observation",
        "subject_ref": _reference_id(resource.get("subject")),
        "encounter_ref": _reference_id(resource.get("encounter")),
        "concept": _concept(resource.get("code")),
        "value": value,
        "unit": unit,
        "temporal": {
            "effective_start": resource.get("effectiveDateTime"),
            "effective_end": None,
            "recorded_at": None,
            "precision": "second" if resource.get("effectiveDateTime") is not None else None,
        },
        "identifiers": _identifiers(resource),
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": attributes,
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="observation",
        subject_ref=payload["subject_ref"],
        semantic_payload=payload,
        target_paths=(path,),
        relationships=tuple(relationships),
    )


def _order_fact(
    resource: dict[str, Any],
    path: str,
    *,
    order_report_links: dict[str, list[str]],
) -> LiftedFact:
    resource_id = str(resource["id"])
    lifted_id = _local_id("ServiceRequest", resource_id)
    relationships = [
        ("has_report", report_id)
        for report_id in order_report_links.get(lifted_id, [])
    ]

    requester_payload: dict[str, Any] | None = None
    requester = resource.get("requester")
    if isinstance(requester, dict):
        requester_payload = {}
        identifier = requester.get("identifier")
        if isinstance(identifier, dict) and identifier.get("value") is not None:
            requester_payload["identifiers"] = [
                {
                    "system": identifier.get("system"),
                    "value": identifier.get("value"),
                    "type": None,
                }
            ]
        if requester.get("display") is not None:
            requester_payload["display"] = requester.get("display")
        if not requester_payload:
            requester_payload = None

    payload = {
        "fact_type": "order",
        "subject_ref": _reference_id(resource.get("subject")),
        "encounter_ref": _reference_id(resource.get("encounter")),
        "concept": _concept(resource.get("code")),
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": None,
            "effective_end": None,
            "recorded_at": resource.get("authoredOn"),
            "precision": "second" if resource.get("authoredOn") is not None else None,
        },
        "identifiers": _identifiers(resource),
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": {
            "lifecycle_status": resource.get("status"),
            "request_intent": resource.get("intent"),
            "requester": requester_payload,
        },
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="order",
        subject_ref=payload["subject_ref"],
        semantic_payload=payload,
        target_paths=(path,),
        relationships=tuple(relationships),
    )


def _report_fact(resource: dict[str, Any], path: str) -> LiftedFact:
    resource_id = str(resource["id"])
    lifted_id = _local_id("DiagnosticReport", resource_id)
    relationships: list[tuple[str, str]] = []
    results = resource.get("result", [])
    if isinstance(results, list):
        for reference in results:
            target = _reference_id(reference)
            if target is not None:
                relationships.append(("has_result", target))
    specimens = resource.get("specimen", [])
    if isinstance(specimens, list):
        for reference in specimens:
            target = _reference_id(reference)
            if target is not None:
                relationships.append(("has_specimen", target))
    based_on = resource.get("basedOn", [])
    if isinstance(based_on, list):
        for reference in based_on:
            target = _reference_id(reference)
            if target is not None:
                relationships.append(("based_on_order", target))

    payload = {
        "fact_type": "diagnostic_report",
        "subject_ref": _reference_id(resource.get("subject")),
        "encounter_ref": _reference_id(resource.get("encounter")),
        "concept": _concept(resource.get("code")),
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": resource.get("effectiveDateTime"),
            "effective_end": None,
            "recorded_at": resource.get("issued"),
            "precision": "second" if resource.get("effectiveDateTime") is not None else None,
        },
        "identifiers": _identifiers(resource),
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": {"status": resource.get("status"), "category": "laboratory"},
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="diagnostic_report",
        subject_ref=payload["subject_ref"],
        semantic_payload=payload,
        target_paths=(path,),
        relationships=tuple(relationships),
    )


def _specimen_fact(
    resource: dict[str, Any],
    path: str,
    *,
    observation_specimen_links: dict[str, list[str]],
) -> LiftedFact:
    resource_id = str(resource["id"])
    lifted_id = _local_id("Specimen", resource_id)
    collection = (
        resource.get("collection") if isinstance(resource.get("collection"), dict) else {}
    )
    specimen_type = resource.get("type") if isinstance(resource.get("type"), dict) else {}
    method = collection.get("method") if isinstance(collection.get("method"), dict) else {}
    relationships = tuple(
        ("specimen_for_observation", observation_id)
        for observation_id in observation_specimen_links.get(lifted_id, [])
    )
    payload = {
        "fact_type": "specimen",
        "subject_ref": _reference_id(resource.get("subject")),
        "encounter_ref": None,
        "concept": None,
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": collection.get("collectedDateTime"),
            "effective_end": None,
            "recorded_at": None,
            "precision": "second" if collection.get("collectedDateTime") is not None else None,
        },
        "identifiers": _identifiers(resource),
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": {
            "type_label": specimen_type.get("text"),
            "collection_method_label": method.get("text"),
        },
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="specimen",
        subject_ref=payload["subject_ref"],
        semantic_payload=payload,
        target_paths=(path,),
        relationships=relationships,
    )


def _inverse_report_links(
    entries: list[tuple[int, dict[str, Any]]],
) -> dict[str, list[str]]:
    links: dict[str, list[str]] = {}
    for _, resource in entries:
        if resource.get("resourceType") != "DiagnosticReport" or resource.get("id") is None:
            continue
        report_id = _local_id("DiagnosticReport", str(resource["id"]))
        results = resource.get("result", [])
        if not isinstance(results, list):
            continue
        for reference in results:
            observation_id = _reference_id(reference)
            if observation_id is None or not observation_id.startswith("fhir::Observation/"):
                continue
            links.setdefault(observation_id, []).append(report_id)
    return links


def _inverse_order_report_links(
    entries: list[tuple[int, dict[str, Any]]],
) -> dict[str, list[str]]:
    links: dict[str, list[str]] = {}
    for _, resource in entries:
        if resource.get("resourceType") != "DiagnosticReport" or resource.get("id") is None:
            continue
        report_id = _local_id("DiagnosticReport", str(resource["id"]))
        based_on = resource.get("basedOn", [])
        if not isinstance(based_on, list):
            continue
        for reference in based_on:
            order_id = _reference_id(reference)
            if order_id is None or not order_id.startswith("fhir::ServiceRequest/"):
                continue
            links.setdefault(order_id, []).append(report_id)
    return links


def _inverse_specimen_links(
    entries: list[tuple[int, dict[str, Any]]],
) -> dict[str, list[str]]:
    links: dict[str, list[str]] = {}
    for _, resource in entries:
        if resource.get("resourceType") != "Observation" or resource.get("id") is None:
            continue
        specimen_id = _reference_id(resource.get("specimen"))
        if specimen_id is None:
            continue
        observation_id = _local_id("Observation", str(resource["id"]))
        links.setdefault(specimen_id, []).append(observation_id)
    return links


class FhirR4LabLifter:
    """Lift the in-scope FHIR R4 laboratory slice into verifier candidates."""

    @property
    def lifter_id(self) -> str:
        return _LIFTER_ID

    @property
    def lifter_version(self) -> str:
        return _LIFTER_VERSION

    def lift(self, artifact: str | dict[str, Any], *, artifact_id: str) -> LiftResult:
        if not isinstance(artifact, dict):
            raise TypeError("FHIR R4 lifter requires a decoded JSON object")
        if artifact.get("resourceType") != "Bundle":
            raise ValueError("FHIR R4 lab lifter currently requires a Bundle artifact")

        warnings: list[LiftWarning] = []
        entries = _resource_entries(artifact)
        observation_report_links = _inverse_report_links(entries)
        observation_specimen_links = _inverse_specimen_links(entries)
        order_report_links = _inverse_order_report_links(entries)

        facts: list[LiftedFact] = []
        for index, resource in entries:
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
            path = f"Bundle.entry[{index}].resource"
            if resource_id is None:
                warnings.append(
                    LiftWarning(
                        code="RESOURCE_WITHOUT_ID",
                        message="In-scope FHIR resource lacked id and was not lifted.",
                        target_paths=(path,),
                    )
                )
                continue
            if resource_type == "Patient":
                facts.append(_patient_fact(resource, path))
            elif resource_type == "Observation":
                facts.append(
                    _observation_fact(
                        resource,
                        path,
                        observation_report_links=observation_report_links,
                    )
                )
            elif resource_type == "DiagnosticReport":
                facts.append(_report_fact(resource, path))
            elif resource_type == "ServiceRequest":
                facts.append(
                    _order_fact(
                        resource,
                        path,
                        order_report_links=order_report_links,
                    )
                )
            elif resource_type == "Specimen":
                facts.append(
                    _specimen_fact(
                        resource,
                        path,
                        observation_specimen_links=observation_specimen_links,
                    )
                )
            else:
                warnings.append(
                    LiftWarning(
                        code="OUT_OF_SLICE_RESOURCE",
                        message=f"FHIR resource type {resource_type!r} was not lifted.",
                        target_paths=(path,),
                    )
                )

        facts.sort(key=lambda fact: fact.lifted_fact_id)
        return LiftResult(
            artifact_id=artifact_id,
            lifter_id=self.lifter_id,
            lifter_version=self.lifter_version,
            source_standard="HL7_FHIR_R4",
            source_profile="US_Core_9.0.0_laboratory_development_slice",
            facts=tuple(facts),
            warnings=tuple(warnings),
            metadata={
                "bundle_entry_count": len(entries),
                "lifted_fact_count": len(facts),
                "renderer_independence": "no_renderer_imports",
            },
        )
