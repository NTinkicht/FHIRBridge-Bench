"""Development clean-room Renderer A for canonical laboratory facts to FHIR R4.

This renderer exists to exercise the benchmark-generation path before Protocol
v1.0 freeze. It emits ordinary FHIR R4 JSON resources and intentionally does
not share semantic mapping code with any lifter or verifier module.

The artifact is not considered US Core-conformant merely because this renderer
sets profile metadata. Conformance remains a separate structural-validation
step using the pinned external validator/profile package.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any

from .base import RenderManifest, RenderResult, RenderWarning

_RENDERER_ID = "fhir-r4-lab-renderer-a"
_RENDERER_VERSION = "0.2.0-dev"

_PATIENT_PROFILE = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
_OBSERVATION_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"
)
_REPORT_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-diagnosticreport-lab"
)
_SPECIMEN_PROFILE = "http://hl7.org/fhir/StructureDefinition/Specimen"
_SERVICEREQUEST_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-servicerequest"
)


def _resource_id(fact_id: str) -> str:
    """Create a deterministic representation-local FHIR id.

    The id deliberately does not reproduce the canonical fact id. This helps
    ensure downstream grounding cannot succeed through raw id equality.
    """

    digest = sha256(fact_id.encode("utf-8")).hexdigest()[:20]
    return f"fb-{digest}"


def _coding(concept: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(concept, dict):
        return None
    coding: dict[str, Any] = {}
    if concept.get("system") is not None:
        coding["system"] = concept["system"]
    if concept.get("code") is not None:
        coding["code"] = concept["code"]
    if concept.get("display") is not None:
        coding["display"] = concept["display"]
    return coding or None


def _codeable_concept(concept: dict[str, Any] | None) -> dict[str, Any]:
    coding = _coding(concept)
    result: dict[str, Any] = {}
    if coding is not None:
        result["coding"] = [coding]
    if isinstance(concept, dict) and concept.get("display"):
        result["text"] = concept["display"]
    return result


def _identifier(identifier: dict[str, Any]) -> dict[str, Any]:
    rendered: dict[str, Any] = {"value": identifier["value"]}
    if identifier.get("system") is not None:
        rendered["system"] = identifier["system"]

    identifier_type = identifier.get("type")
    if isinstance(identifier_type, str) and identifier_type:
        # Preserve the authored type label without manufacturing a code that
        # falls outside FHIR R4 IdentifierType. MR is in the bound value set;
        # PI is retained as text only because the validator rejects v2-0203#PI
        # for Identifier.type under the base R4 binding.
        rendered["type"] = {"text": identifier_type}
        if identifier_type == "MR":
            rendered["type"]["coding"] = [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                    "code": "MR",
                }
            ]
    return rendered


def _reference(resource_type: str, resource_id: str) -> dict[str, str]:
    return {"reference": f"{resource_type}/{resource_id}"}


def _quantity(value: Any, unit: dict[str, Any] | None) -> dict[str, Any]:
    quantity: dict[str, Any] = {"value": value}
    if isinstance(unit, dict):
        if unit.get("display") is not None:
            quantity["unit"] = unit["display"]
        if unit.get("system") is not None:
            quantity["system"] = unit["system"]
        if unit.get("code") is not None:
            quantity["code"] = unit["code"]
    return quantity


def _find_relation(fact: dict[str, Any], relation_type: str) -> list[str]:
    return [
        relation["target_fact_id"]
        for relation in fact.get("relations", [])
        if relation.get("relation_type") == relation_type
        and isinstance(relation.get("target_fact_id"), str)
    ]


def _patient_resource(fact: dict[str, Any], resource_id: str) -> dict[str, Any]:
    attributes = fact.get("attributes", {})
    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": resource_id,
        "meta": {"profile": [_PATIENT_PROFILE]},
        "identifier": [_identifier(item) for item in fact.get("identifiers", [])],
    }
    name = attributes.get("name")
    if isinstance(name, dict):
        resource["name"] = [deepcopy(name)]
    birth_date = attributes.get("birthDate")
    if birth_date is not None:
        resource["birthDate"] = birth_date
    return resource


def _observation_resource(
    fact: dict[str, Any],
    resource_id: str,
    *,
    resource_ids: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    attributes = fact.get("attributes", {})
    status = attributes.get("status", "unknown")
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": resource_id,
        "meta": {"profile": [_OBSERVATION_PROFILE]},
        "status": status,
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "code": _codeable_concept(fact.get("concept")),
    }

    subject_ref = fact.get("subject_ref")
    if subject_ref in resource_ids:
        subject_type, subject_id = resource_ids[subject_ref]
        resource["subject"] = _reference(subject_type, subject_id)

    temporal = fact.get("temporal")
    if isinstance(temporal, dict) and temporal.get("effective_start") is not None:
        resource["effectiveDateTime"] = temporal["effective_start"]

    value = fact.get("value")
    unit = fact.get("unit")
    value_code = attributes.get("value_code")
    if isinstance(value_code, dict):
        coded_value = _codeable_concept(value_code)
        if value is not None:
            coded_value["text"] = str(value)
        resource["valueCodeableConcept"] = coded_value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        resource["valueQuantity"] = _quantity(value, unit)
    elif isinstance(value, bool):
        resource["valueBoolean"] = value
    elif value is not None:
        resource["valueString"] = str(value)

    reference_range = attributes.get("reference_range")
    if isinstance(reference_range, dict):
        range_unit = {
            "system": "http://unitsofmeasure.org",
            "code": reference_range.get("unit"),
            "display": reference_range.get("unit"),
        }
        rendered_range: dict[str, Any] = {}
        if reference_range.get("low") is not None:
            rendered_range["low"] = _quantity(reference_range["low"], range_unit)
        if reference_range.get("high") is not None:
            rendered_range["high"] = _quantity(reference_range["high"], range_unit)
        if rendered_range:
            resource["referenceRange"] = [rendered_range]

    interpretation = attributes.get("interpretation")
    if isinstance(interpretation, dict):
        resource["interpretation"] = [
            {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/CodeSystem/"
                            "v3-ObservationInterpretation"
                        ),
                        "code": interpretation.get("code"),
                        "display": interpretation.get("display"),
                    }
                ]
            }
        ]

    # Report membership is represented by DiagnosticReport.result. We do not
    # encode a synthetic inverse through Observation.derivedFrom because a
    # DiagnosticReport is not the semantic source of the observation result.
    specimen_refs = _find_relation(fact, "specimen")
    if specimen_refs:
        specimen_fact_id = specimen_refs[0]
        if specimen_fact_id in resource_ids:
            specimen_type, specimen_id = resource_ids[specimen_fact_id]
            resource["specimen"] = _reference(specimen_type, specimen_id)

    return resource


def _specimen_resource(
    fact: dict[str, Any],
    resource_id: str,
    *,
    resource_ids: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    attributes = fact.get("attributes", {})
    resource: dict[str, Any] = {
        "resourceType": "Specimen",
        "id": resource_id,
        "meta": {"profile": [_SPECIMEN_PROFILE]},
        "identifier": [_identifier(item) for item in fact.get("identifiers", [])],
    }

    subject_ref = fact.get("subject_ref")
    if subject_ref in resource_ids:
        subject_type, subject_id = resource_ids[subject_ref]
        resource["subject"] = _reference(subject_type, subject_id)

    type_label = attributes.get("type_label")
    if type_label is not None:
        resource["type"] = {"text": str(type_label)}

    collection: dict[str, Any] = {}
    method_label = attributes.get("collection_method_label")
    if method_label is not None:
        collection["method"] = {"text": str(method_label)}
    temporal = fact.get("temporal")
    if isinstance(temporal, dict) and temporal.get("effective_start") is not None:
        collection["collectedDateTime"] = temporal["effective_start"]
    if collection:
        resource["collection"] = collection

    return resource


def _order_resource(
    fact: dict[str, Any],
    resource_id: str,
    *,
    resource_ids: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    attributes = fact.get("attributes", {})
    resource: dict[str, Any] = {
        "resourceType": "ServiceRequest",
        "id": resource_id,
        "meta": {"profile": [_SERVICEREQUEST_PROFILE]},
        "status": attributes.get("lifecycle_status", "unknown"),
        "intent": attributes.get("request_intent", "order"),
        "code": _codeable_concept(fact.get("concept")),
        "identifier": [_identifier(item) for item in fact.get("identifiers", [])],
    }

    subject_ref = fact.get("subject_ref")
    if subject_ref in resource_ids:
        subject_type, subject_id = resource_ids[subject_ref]
        resource["subject"] = _reference(subject_type, subject_id)

    temporal = fact.get("temporal")
    if isinstance(temporal, dict) and temporal.get("recorded_at") is not None:
        resource["authoredOn"] = temporal["recorded_at"]

    requester = attributes.get("requester")
    if isinstance(requester, dict):
        requester_reference: dict[str, Any] = {"type": "Practitioner"}
        requester_identifiers = requester.get("identifiers", [])
        requester_identifier = next(
            (
                item
                for item in requester_identifiers
                if isinstance(item, dict) and item.get("value")
            ),
            None,
        )
        if requester_identifier is not None:
            requester_reference["identifier"] = _identifier(requester_identifier)
        if requester.get("display"):
            requester_reference["display"] = str(requester["display"])
        if len(requester_reference) > 1:
            resource["requester"] = requester_reference

    return resource


def _report_resource(
    fact: dict[str, Any],
    resource_id: str,
    *,
    resource_ids: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    attributes = fact.get("attributes", {})
    resource: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": resource_id,
        "meta": {"profile": [_REPORT_PROFILE]},
        "status": attributes.get("status", "unknown"),
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "LAB",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "code": _codeable_concept(fact.get("concept")),
        "identifier": [_identifier(item) for item in fact.get("identifiers", [])],
    }

    subject_ref = fact.get("subject_ref")
    if subject_ref in resource_ids:
        subject_type, subject_id = resource_ids[subject_ref]
        resource["subject"] = _reference(subject_type, subject_id)

    temporal = fact.get("temporal")
    if isinstance(temporal, dict):
        if temporal.get("effective_start") is not None:
            resource["effectiveDateTime"] = temporal["effective_start"]
        if temporal.get("recorded_at") is not None:
            resource["issued"] = temporal["recorded_at"]

    result_refs: list[dict[str, str]] = []
    for target_fact_id in _find_relation(fact, "has_result"):
        target = resource_ids.get(target_fact_id)
        if target is not None:
            result_refs.append(_reference(*target))
    if result_refs:
        resource["result"] = result_refs

    specimen_refs: list[dict[str, str]] = []
    for target_fact_id in _find_relation(fact, "has_specimen"):
        target = resource_ids.get(target_fact_id)
        if target is not None:
            specimen_refs.append(_reference(*target))
    if specimen_refs:
        resource["specimen"] = specimen_refs

    based_on_refs: list[dict[str, str]] = []
    for target_fact_id in _find_relation(fact, "based_on_order"):
        target = resource_ids.get(target_fact_id)
        if target is not None:
            based_on_refs.append(_reference(*target))
    if based_on_refs:
        resource["basedOn"] = based_on_refs

    return resource


class FhirR4LabRendererA:
    """Development Renderer A for the laboratory canonical slice."""

    @property
    def renderer_id(self) -> str:
        return _RENDERER_ID

    @property
    def renderer_version(self) -> str:
        return _RENDERER_VERSION

    def render(
        self,
        graph: dict[str, Any],
        *,
        contract: dict[str, Any],
    ) -> RenderResult:
        contract_header = contract.get("contract", {})
        resource_ids: dict[str, tuple[str, str]] = {}
        warnings: list[RenderWarning] = []

        type_map = {
            "patient_identity": "Patient",
            "diagnostic_report": "DiagnosticReport",
            "observation": "Observation",
            "specimen": "Specimen",
            "order": "ServiceRequest",
        }
        for fact in graph.get("facts", []):
            resource_type = type_map.get(fact.get("fact_type"))
            if resource_type is None:
                warnings.append(
                    RenderWarning(
                        code="UNSUPPORTED_FACT_TYPE",
                        message=(
                            "Development FHIR renderer skipped an out-of-slice "
                            f"fact type: {fact.get('fact_type')!r}"
                        ),
                        fact_ids=(str(fact.get("fact_id")),),
                    )
                )
                continue
            resource_ids[fact["fact_id"]] = (
                resource_type,
                _resource_id(fact["fact_id"]),
            )

        entries: list[dict[str, Any]] = []
        for fact in graph.get("facts", []):
            mapped = resource_ids.get(fact.get("fact_id"))
            if mapped is None:
                continue
            resource_type, resource_id = mapped
            if resource_type == "Patient":
                resource = _patient_resource(fact, resource_id)
            elif resource_type == "Observation":
                resource = _observation_resource(
                    fact,
                    resource_id,
                    resource_ids=resource_ids,
                )
            elif resource_type == "Specimen":
                resource = _specimen_resource(
                    fact,
                    resource_id,
                    resource_ids=resource_ids,
                )
            elif resource_type == "DiagnosticReport":
                resource = _report_resource(
                    fact,
                    resource_id,
                    resource_ids=resource_ids,
                )
            elif resource_type == "ServiceRequest":
                resource = _order_resource(
                    fact,
                    resource_id,
                    resource_ids=resource_ids,
                )
            else:  # pragma: no cover - guarded by type_map
                continue
            entries.append(
                {
                    "fullUrl": (
                        f"https://fhirbridge.example/fhir/{resource_type}/{resource_id}"
                    ),
                    "resource": resource,
                }
            )

        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": entries,
        }
        manifest = RenderManifest(
            graph_id=str(graph.get("graph_id", "unknown")),
            renderer_id=self.renderer_id,
            renderer_version=self.renderer_version,
            contract_id=str(contract_header.get("id", "unknown")),
            contract_version=str(contract_header.get("version", "unknown")),
            target_standard="HL7_FHIR_R4",
            target_profile="US_Core_9.0.0_laboratory_development_slice",
            warnings=tuple(warnings),
            metadata={
                "resource_count": len(entries),
                "clean_room_role": "renderer_a_development",
                "structural_validation_status": "not_run_by_renderer",
            },
        )
        return RenderResult(
            media_type="application/fhir+json",
            artifact=bundle,
            manifest=manifest,
        )
