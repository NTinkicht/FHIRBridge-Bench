"""Development clean-room Renderer A for canonical lab facts to HL7 v2.5.1 ORU^R01.

The implementation is intentionally small and profile-scoped. It serializes the
current laboratory reference slice without importing lifter or verifier logic.
Renderer output is not treated as semantic ground truth; it is one independent
realization used to exercise the measurement path before Protocol v1.0 freeze.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

from .base import RenderManifest, RenderResult, RenderWarning

_RENDERER_ID = "hl7v251-lri-oru-renderer-a"
_RENDERER_VERSION = "0.2.0-dev"


def _segment(name: str, fields: dict[int, str]) -> str:
    maximum = max(fields, default=0)
    values = [""] * maximum
    for number, value in fields.items():
        values[number - 1] = value
    return name + "|" + "|".join(values)


def _hl7_ts(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if "T" not in value:
        return value.replace("-", "")
    dt = datetime.fromisoformat(value)
    text = dt.strftime("%Y%m%d%H%M%S")
    offset = dt.utcoffset()
    if offset is not None:
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        total_minutes = abs(total_minutes)
        text += f"{sign}{total_minutes // 60:02d}{total_minutes % 60:02d}"
    return text


def _escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("\\", "\\E\\")
        .replace("|", "\\F\\")
        .replace("^", "\\S\\")
        .replace("~", "\\R\\")
        .replace("&", "\\T\\")
    )


def _system_alias(system: Any) -> str:
    aliases = {
        "http://loinc.org": "LN",
        "http://unitsofmeasure.org": "UCUM",
        "urn:fhirbridge:synthetic:lab": "FBRLAB",
        "urn:fhirbridge:synthetic:result": "FBRRES",
    }
    if system is None:
        return ""
    return aliases.get(str(system), str(system))


def _ce(concept: dict[str, Any] | None) -> str:
    if not isinstance(concept, dict):
        return ""
    return "^".join(
        [
            _escape(concept.get("code")),
            _escape(concept.get("display")),
            _escape(_system_alias(concept.get("system"))),
        ]
    )


def _identifier_cx(identifier: dict[str, Any]) -> str:
    return "^".join(
        [
            _escape(identifier.get("value")),
            "",
            "",
            _escape(identifier.get("system")),
            _escape(identifier.get("type")),
        ]
    )


def _identifier_ei(identifier: dict[str, Any]) -> str:
    return "^".join(
        [
            _escape(identifier.get("value")),
            _escape(identifier.get("system")),
        ]
    )


def _status_code(status: Any) -> str:
    mapping = {
        "registered": "R",
        "partial": "P",
        "preliminary": "P",
        "final": "F",
        "amended": "C",
        "corrected": "C",
        "appended": "C",
        "cancelled": "X",
        "entered-in-error": "X",
    }
    return mapping.get(str(status), "U")


def _reference_range(attributes: dict[str, Any]) -> str:
    value = attributes.get("reference_range")
    if not isinstance(value, dict):
        return ""
    low = value.get("low")
    high = value.get("high")
    if low is None and high is None:
        return ""
    if low is None:
        return f"-{_escape(high)}"
    if high is None:
        return f"{_escape(low)}-"
    return f"{_escape(low)}-{_escape(high)}"


def _unit_ce(unit: dict[str, Any] | None) -> str:
    if not isinstance(unit, dict):
        return ""
    return "^".join(
        [
            _escape(unit.get("code")),
            _escape(unit.get("display")),
            _escape(_system_alias(unit.get("system"))),
        ]
    )


def _obx_value(fact: dict[str, Any]) -> tuple[str, str]:
    attributes = fact.get("attributes", {})
    coded = attributes.get("value_code") if isinstance(attributes, dict) else None
    if isinstance(coded, dict):
        return "CWE", _ce(coded)
    value = fact.get("value")
    if isinstance(value, bool):
        return "ST", "true" if value else "false"
    if isinstance(value, (int, float)):
        return "NM", _escape(value)
    return "ST", _escape(value)


def _message_control_id(graph_id: str) -> str:
    return "FB" + sha256(graph_id.encode("utf-8")).hexdigest()[:14].upper()


def _first_fact(graph: dict[str, Any], fact_type: str) -> dict[str, Any] | None:
    return next(
        (fact for fact in graph.get("facts", []) if fact.get("fact_type") == fact_type),
        None,
    )


def _facts(graph: dict[str, Any], fact_type: str) -> list[dict[str, Any]]:
    return [fact for fact in graph.get("facts", []) if fact.get("fact_type") == fact_type]


def _relation_targets(fact: dict[str, Any], relation_type: str) -> list[str]:
    return [
        relation["target_fact_id"]
        for relation in fact.get("relations", [])
        if relation.get("relation_type") == relation_type
        and isinstance(relation.get("target_fact_id"), str)
    ]


class Hl7V251OruRendererA:
    """Render the development laboratory slice as one v2.5.1 ORU^R01 message."""

    @property
    def renderer_id(self) -> str:
        return _RENDERER_ID

    @property
    def renderer_version(self) -> str:
        return _RENDERER_VERSION

    def _render_obx(self, observation: dict[str, Any], *, set_id: int) -> str:
        attributes = observation.get("attributes", {})
        temporal = observation.get("temporal", {})
        value_type, value = _obx_value(observation)
        interpretation = attributes.get("interpretation")
        interpretation_code = (
            _escape(interpretation.get("code"))
            if isinstance(interpretation, dict)
            else ""
        )
        return _segment(
            "OBX",
            {
                1: str(set_id),
                2: value_type,
                3: _ce(observation.get("concept")),
                5: value,
                6: _unit_ce(observation.get("unit")),
                7: _reference_range(attributes),
                8: interpretation_code,
                11: _status_code(attributes.get("status")),
                14: _hl7_ts(temporal.get("effective_start")),
            },
        )

    def render(
        self,
        graph: dict[str, Any],
        *,
        contract: dict[str, Any],
    ) -> RenderResult:
        contract_header = contract.get("contract", {})
        warnings: list[RenderWarning] = []
        patient = _first_fact(graph, "patient_identity")
        reports = _facts(graph, "diagnostic_report")
        observations = _facts(graph, "observation")
        specimens = _facts(graph, "specimen")
        if patient is None or not reports:
            raise ValueError(
                "HL7 v2 lab renderer requires patient_identity and diagnostic_report"
            )

        graph_id = str(graph.get("graph_id", "unknown"))
        control_id = _message_control_id(graph_id)
        report_temporal = reports[0].get("temporal", {})
        message_time = _hl7_ts(
            report_temporal.get("recorded_at") or report_temporal.get("effective_start")
        )
        msh = (
            "MSH|^~\\&|FHIRBRIDGE|REFERENCE|BENCHMARK|REFERENCE|"
            f"{message_time}||ORU^R01^ORU_R01|{control_id}|P|2.5.1"
        )

        patient_attributes = patient.get("attributes", {})
        patient_identifiers = patient.get("identifiers", [])
        pid3 = "~".join(
            _identifier_cx(identifier)
            for identifier in patient_identifiers
            if isinstance(identifier, dict)
        )
        name = patient_attributes.get("name") if isinstance(patient_attributes, dict) else None
        pid5 = ""
        if isinstance(name, dict):
            given = name.get("given")
            first_given = given[0] if isinstance(given, list) and given else ""
            pid5 = "^".join([_escape(name.get("family")), _escape(first_given)])
        pid = _segment(
            "PID",
            {
                1: "1",
                3: pid3,
                5: pid5,
                7: _hl7_ts(patient_attributes.get("birthDate")),
            },
        )

        segments = [msh, pid]
        observations_by_id = {
            str(fact.get("fact_id")): fact
            for fact in observations
            if fact.get("fact_id") is not None
        }
        specimens_by_id = {
            str(fact.get("fact_id")): fact
            for fact in specimens
            if fact.get("fact_id") is not None
        }
        rendered_observation_ids: set[str] = set()
        rendered_specimen_ids: set[str] = set()

        for report_set_id, report in enumerate(reports, start=1):
            report_id = str(report.get("fact_id"))
            report_attributes = report.get("attributes", {})
            report_temporal = report.get("temporal", {})
            segments.append(
                _segment(
                    "OBR",
                    {
                        1: str(report_set_id),
                        4: _ce(report.get("concept")),
                        7: _hl7_ts(report_temporal.get("effective_start")),
                        22: _hl7_ts(report_temporal.get("recorded_at")),
                        25: _status_code(report_attributes.get("status")),
                    },
                )
            )

            allowed_observation_ids = _relation_targets(report, "has_result")
            if not allowed_observation_ids:
                allowed_observation_ids = [
                    str(observation.get("fact_id"))
                    for observation in observations
                    if report_id
                    in _relation_targets(observation, "belongs_to_report")
                ]
            report_observations = [
                observations_by_id[observation_id]
                for observation_id in allowed_observation_ids
                if observation_id in observations_by_id
            ]

            report_specimen_ids = _relation_targets(report, "has_specimen")
            for observation in report_observations:
                for specimen_id in _relation_targets(observation, "specimen"):
                    if specimen_id not in report_specimen_ids:
                        report_specimen_ids.append(specimen_id)

            obx_set_id = 1
            for spm_set_id, specimen_id in enumerate(report_specimen_ids, start=1):
                specimen = specimens_by_id.get(specimen_id)
                if specimen is None:
                    warnings.append(
                        RenderWarning(
                            code="REPORT_SPECIMEN_NOT_FOUND",
                            message=(
                                "Report referenced a specimen that was absent from "
                                "the canonical graph."
                            ),
                            fact_ids=(report_id, specimen_id),
                        )
                    )
                    continue

                specimen_identifiers = specimen.get("identifiers", [])
                specimen_attributes = specimen.get("attributes", {})
                specimen_temporal = specimen.get("temporal", {})
                specimen_identifier = next(
                    (
                        _identifier_ei(identifier)
                        for identifier in specimen_identifiers
                        if isinstance(identifier, dict)
                    ),
                    "",
                )
                segments.append(
                    _segment(
                        "SPM",
                        {
                            1: str(spm_set_id),
                            2: specimen_identifier,
                            4: "^".join(
                                [
                                    _escape(specimen_attributes.get("type_label")),
                                    _escape(specimen_attributes.get("type_label")),
                                    "FBR-SPEC",
                                ]
                            ),
                            7: "^".join(
                                [
                                    _escape(
                                        specimen_attributes.get(
                                            "collection_method_label"
                                        )
                                    ),
                                    _escape(
                                        specimen_attributes.get(
                                            "collection_method_label"
                                        )
                                    ),
                                    "FBR-METHOD",
                                ]
                            ),
                            17: _hl7_ts(
                                specimen_temporal.get("effective_start")
                            ),
                        },
                    )
                )
                rendered_specimen_ids.add(specimen_id)

                for observation in report_observations:
                    observation_id = str(observation.get("fact_id"))
                    if observation_id in rendered_observation_ids:
                        continue
                    if specimen_id not in _relation_targets(
                        observation,
                        "specimen",
                    ):
                        continue
                    segments.append(
                        self._render_obx(observation, set_id=obx_set_id)
                    )
                    rendered_observation_ids.add(observation_id)
                    obx_set_id += 1

            for observation in report_observations:
                observation_id = str(observation.get("fact_id"))
                if observation_id in rendered_observation_ids:
                    continue
                segments.append(self._render_obx(observation, set_id=obx_set_id))
                rendered_observation_ids.add(observation_id)
                obx_set_id += 1

        for observation in observations:
            observation_id = str(observation.get("fact_id"))
            if observation_id not in rendered_observation_ids:
                warnings.append(
                    RenderWarning(
                        code="OBSERVATION_NOT_LINKED_TO_REPORT",
                        message=(
                            "Observation was skipped because it was not linked to "
                            "a rendered report."
                        ),
                        fact_ids=(observation_id,),
                    )
                )

        for specimen in specimens:
            specimen_id = str(specimen.get("fact_id"))
            if specimen_id not in rendered_specimen_ids:
                warnings.append(
                    RenderWarning(
                        code="SPECIMEN_NOT_LINKED_TO_REPORT",
                        message=(
                            "Specimen was skipped because it was not linked to a "
                            "rendered report or observation."
                        ),
                        fact_ids=(specimen_id,),
                    )
                )

        manifest = RenderManifest(
            graph_id=graph_id,
            renderer_id=self.renderer_id,
            renderer_version=self.renderer_version,
            contract_id=str(contract_header.get("id", "unknown")),
            contract_version=str(contract_header.get("version", "unknown")),
            target_standard="HL7_v2.5.1",
            target_profile="LRI_Edition_5_ORU_R01_development_slice",
            warnings=tuple(warnings),
            metadata={
                "segment_count": len(segments),
                "observation_count": sum(
                    1 for segment in segments if segment.startswith("OBX|")
                ),
                "report_count": sum(
                    1 for segment in segments if segment.startswith("OBR|")
                ),
                "specimen_count": sum(
                    1 for segment in segments if segment.startswith("SPM|")
                ),
                "clean_room_role": "renderer_a_development",
                "structural_validation_status": "not_run_by_renderer",
            },
        )
        return RenderResult(
            media_type="x-application/hl7-v2+er7",
            artifact="\r".join(segments) + "\r",
            manifest=manifest,
        )
