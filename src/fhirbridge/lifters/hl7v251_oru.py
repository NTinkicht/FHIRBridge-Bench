"""Independent HL7 v2.5.1 ORU^R01 laboratory artifact lifter.

The parser reconstructs candidate canonical facts from ER7 text. It does not
import reference-renderer mapping functions and does not decide semantic
correctness. Equivalence and projectability remain verifier responsibilities.
"""

from __future__ import annotations

from typing import Any

from fhirbridge.verifier.model import LiftedFact

from .base import LiftResult, LiftWarning

_LIFTER_ID = "hl7v251-lri-oru-lifter"
_LIFTER_VERSION = "0.4.0-dev"


def _unescape(value: str) -> str:
    return (
        value.replace("\\F\\", "|")
        .replace("\\S\\", "^")
        .replace("\\R\\", "~")
        .replace("\\T\\", "&")
        .replace("\\E\\", "\\")
    )


def _field(segment: list[str], number: int) -> str:
    return segment[number] if number < len(segment) else ""


def _components(value: str) -> list[str]:
    return [_unescape(item) for item in value.split("^")]


def _component(value: str, number: int) -> str | None:
    values = _components(value)
    index = number - 1
    if index >= len(values) or values[index] == "":
        return None
    return values[index]


def _system_uri(alias: str | None) -> str | None:
    aliases = {
        "LN": "http://loinc.org",
        "UCUM": "http://unitsofmeasure.org",
        "FBRLAB": "urn:fhirbridge:synthetic:lab",
        "FBRRES": "urn:fhirbridge:synthetic:result",
    }
    if alias is None:
        return None
    return aliases.get(alias, alias)


def _concept(value: str) -> dict[str, Any] | None:
    code = _component(value, 1)
    display = _component(value, 2)
    system = _system_uri(_component(value, 3))
    if code is None and display is None and system is None:
        return None
    return {
        "system": system,
        "code": code,
        "display": display,
        "local_code": None,
    }


def _ts_to_iso(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    if len(value) < 14 or not value[:14].isdigit():
        return value
    result = (
        f"{value[0:4]}-{value[4:6]}-{value[6:8]}T"
        f"{value[8:10]}:{value[10:12]}:{value[12:14]}"
    )
    suffix = value[14:]
    if len(suffix) == 5 and suffix[0] in "+-" and suffix[1:].isdigit():
        result += f"{suffix[0]}{suffix[1:3]}:{suffix[3:5]}"
    return result


def _number(value: str) -> int | float | str | None:
    if value == "":
        return None
    try:
        if "." not in value and "e" not in value.lower():
            return int(value)
        return float(value)
    except ValueError:
        return _unescape(value)


def _report_status(status: str) -> str | None:
    """Map OBR-25 using the evidence-backed v2 -> FHIR candidate only."""

    mapping = {
        "O": "registered",
        "I": "registered",
        "S": "registered",
        "P": "preliminary",
        "C": "corrected",
        "R": "partial",
        "F": "final",
        "X": "cancelled",
    }
    return mapping.get(status) if status else None


def _observation_status(status: str) -> str | None:
    """Map OBX-11 using the evidence-backed v2 -> FHIR candidate only."""

    mapping = {
        "A": "amended",
        "C": "corrected",
        "D": "entered-in-error",
        "F": "final",
        "P": "preliminary",
        "X": "cancelled",
        "W": "entered-in-error",
    }
    return mapping.get(status) if status else None


def _interpretation(code: str) -> dict[str, Any] | None:
    if not code:
        return None
    displays = {"N": "Normal", "H": "High", "L": "Low"}
    return {"code": code, "display": displays.get(code)}


def _identifier_from_cx(value: str) -> dict[str, Any] | None:
    parts = _components(value)
    identifier_value = parts[0] if parts else ""
    if not identifier_value:
        return None
    system = parts[3] if len(parts) > 3 and parts[3] else None
    identifier_type = parts[4] if len(parts) > 4 and parts[4] else None
    return {"system": system, "value": identifier_value, "type": identifier_type}


def _identifier_from_ei(value: str) -> dict[str, Any] | None:
    parts = _components(value)
    if not parts or not parts[0]:
        return None
    return {
        "system": parts[1] if len(parts) > 1 and parts[1] else None,
        "value": parts[0],
        "type": "specimen",
    }


def _order_identifier_from_ei(
    value: str, *, identifier_kind: str
) -> dict[str, Any] | None:
    """Lift the asserted placer/filler kind without inferring FHIR equivalence."""

    if identifier_kind not in {"placer", "filler"}:
        raise ValueError("order identifier kind must be placer or filler")
    parts = _components(value)
    if not parts or not parts[0]:
        return None
    return {
        "system": parts[1] if len(parts) > 1 and parts[1] else None,
        "value": parts[0],
        "type": identifier_kind,
    }


def _requester_from_xcn(value: str) -> dict[str, Any] | None:
    if not value:
        return None
    identifier_value = _component(value, 1)
    family = _component(value, 2)
    given = _component(value, 3)
    assigning_authority = _component(value, 9)

    requester: dict[str, Any] = {}
    if identifier_value is not None:
        requester["identifiers"] = [
            {
                "system": assigning_authority,
                "value": identifier_value,
                "type": "provider",
            }
        ]
    display_parts = [part for part in (given, family) if part]
    if display_parts:
        requester["display"] = " ".join(display_parts)
    return requester or None


def _merge_identifiers(*identifiers: dict[str, Any] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            continue
        key = (
            identifier.get("system"),
            identifier.get("value"),
            identifier.get("type"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(identifier)
    return result


def _merge_requesters(*requesters: dict[str, Any] | None) -> dict[str, Any] | None:
    identifiers: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    displays: list[str] = []
    for requester in requesters:
        if not isinstance(requester, dict):
            continue
        for identifier in requester.get("identifiers", []):
            if not isinstance(identifier, dict):
                continue
            key = (identifier.get("system"), identifier.get("value"))
            if key in seen:
                continue
            seen.add(key)
            identifiers.append(identifier)
        display = requester.get("display")
        if isinstance(display, str) and display and display not in displays:
            displays.append(display)
    if not identifiers and not displays:
        return None
    result: dict[str, Any] = {"identifiers": identifiers}
    if displays:
        result["display"] = " | ".join(displays)
    return result


def _unit(value: str) -> dict[str, Any] | None:
    if not value:
        return None
    code = _component(value, 1)
    display = _component(value, 2)
    system = _system_uri(_component(value, 3))
    if code is None and display is None and system is None:
        return None
    return {"system": system, "code": code, "display": display}


def _reference_range(
    value: str,
    unit: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not value or "-" not in value:
        return None
    low, high = value.split("-", 1)
    result = {
        "low": _number(low),
        "high": _number(high),
        "unit": unit.get("code") if isinstance(unit, dict) else None,
    }
    return result


def _parse_segments(artifact: str) -> list[list[str]]:
    normalized = artifact.replace("\n", "\r")
    return [line.split("|") for line in normalized.split("\r") if line.strip()]


def _segment_index(
    segments: list[list[str]],
    name: str,
) -> list[tuple[int, list[str]]]:
    return [
        (index, segment)
        for index, segment in enumerate(segments)
        if segment[0] == name
    ]


def _patient_fact(pid: list[str], path: str) -> LiftedFact:
    identifiers = [
        identifier
        for repetition in _field(pid, 3).split("~")
        if repetition
        if (identifier := _identifier_from_cx(repetition)) is not None
    ]
    family = _component(_field(pid, 5), 1)
    given = _component(_field(pid, 5), 2)
    name = None
    if family is not None or given is not None:
        name = {"family": family, "given": [given] if given is not None else []}
    birth_date = _ts_to_iso(_field(pid, 7))
    identity_token = identifiers[0]["value"] if identifiers else "unidentified"
    lifted_id = f"v2::patient::{identity_token}"
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
            "precision": "day" if birth_date else None,
        },
        "identifiers": identifiers,
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


def _report_fact(
    obr: list[str],
    path: str,
    *,
    patient_id: str,
    report_id: str,
    observation_ids: list[str],
    specimen_ids: list[str],
    order_id: str | None = None,
) -> LiftedFact:
    lifted_id = report_id
    relationships = [
        ("has_result", observation_id) for observation_id in observation_ids
    ]
    relationships.extend(
        ("has_specimen", specimen_id) for specimen_id in specimen_ids
    )
    if order_id is not None:
        relationships.append(("based_on_order", order_id))
    effective = _ts_to_iso(_field(obr, 7))
    issued = _ts_to_iso(_field(obr, 22))
    payload = {
        "fact_type": "diagnostic_report",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": _concept(_field(obr, 4)),
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": effective,
            "effective_end": None,
            "recorded_at": issued,
            "precision": "second" if effective else None,
        },
        "identifiers": [],
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": {
            "status": _report_status(_field(obr, 25)),
            "category": "laboratory",
        },
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="diagnostic_report",
        subject_ref=patient_id,
        semantic_payload=payload,
        target_paths=(path,),
        relationships=tuple(relationships),
    )


def _order_fact(
    orc: list[str] | None,
    obr: list[str],
    *,
    orc_path: str | None,
    obr_path: str,
    patient_id: str,
    report_id: str,
    lifted_id: str,
) -> LiftedFact | None:
    # ORC-2/OBR-2 assert placer IDs; ORC-3/OBR-3 assert filler IDs.
    # Preserve both kinds and conflicting assertions. This does not license
    # either source identifier as the uniquely correct filler/placer mapping.
    orc_placer = (
        _order_identifier_from_ei(_field(orc, 2), identifier_kind="placer")
        if orc is not None
        else None
    )
    obr_placer = _order_identifier_from_ei(
        _field(obr, 2), identifier_kind="placer"
    )
    orc_filler = (
        _order_identifier_from_ei(_field(orc, 3), identifier_kind="filler")
        if orc is not None
        else None
    )
    obr_filler = _order_identifier_from_ei(
        _field(obr, 3), identifier_kind="filler"
    )
    identifiers = _merge_identifiers(
        orc_placer, obr_placer, orc_filler, obr_filler
    )

    orc_requester = _requester_from_xcn(_field(orc, 12)) if orc is not None else None
    obr_requester = _requester_from_xcn(_field(obr, 16))
    requester = _merge_requesters(orc_requester, obr_requester)

    if not identifiers and requester is None and orc is None:
        return None

    relationships = [("has_report", report_id)]
    target_paths = [obr_path]
    if orc_path is not None:
        target_paths.insert(0, orc_path)

    payload = {
        "fact_type": "order",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": _concept(_field(obr, 4)),
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": None,
            "effective_end": None,
            "recorded_at": None,
            "precision": None,
        },
        "identifiers": identifiers,
        "relations": [
            {"relation_type": "has_report", "target_fact_id": report_id}
        ],
        "attributes": {
            "order_control_observed": _field(orc, 1) if orc is not None else None,
            "requester": requester,
        },
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="order",
        subject_ref=patient_id,
        semantic_payload=payload,
        target_paths=tuple(target_paths),
        relationships=tuple(relationships),
    )


def _observation_fact(
    obx: list[str],
    path: str,
    *,
    patient_id: str,
    report_id: str,
    specimen_id: str | None,
    lifted_id: str,
) -> LiftedFact:
    value_type = _field(obx, 2)
    raw_value = _field(obx, 5)
    attributes: dict[str, Any] = {"status": _observation_status(_field(obx, 11))}
    unit = _unit(_field(obx, 6))
    if value_type in {"CWE", "CE"}:
        coded = _concept(raw_value)
        if coded is not None:
            attributes["value_code"] = {
                "system": coded.get("system"),
                "code": coded.get("code"),
                "display": coded.get("display"),
            }
        display = coded.get("display") if coded is not None else None
        value: Any = display.lower() if isinstance(display, str) else None
        unit = None
    elif value_type == "NM":
        value = _number(raw_value)
    elif value_type == "ST":
        lowered = _unescape(raw_value).lower()
        if lowered == "true":
            value = True
        elif lowered == "false":
            value = False
        else:
            value = _unescape(raw_value)
    else:
        value = _unescape(raw_value) if raw_value else None

    reference_range = _reference_range(_field(obx, 7), unit)
    if reference_range is not None:
        attributes["reference_range"] = reference_range
    interpretation = _interpretation(_field(obx, 8))
    if interpretation is not None:
        attributes["interpretation"] = interpretation

    relationships = [("belongs_to_report", report_id)]
    if specimen_id is not None:
        relationships.append(("specimen", specimen_id))
    effective = _ts_to_iso(_field(obx, 14))
    payload = {
        "fact_type": "observation",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": _concept(_field(obx, 3)),
        "value": value,
        "unit": unit,
        "temporal": {
            "effective_start": effective,
            "effective_end": None,
            "recorded_at": None,
            "precision": "second" if effective else None,
        },
        "identifiers": [],
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": attributes,
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="observation",
        subject_ref=patient_id,
        semantic_payload=payload,
        target_paths=(path,),
        relationships=tuple(relationships),
    )


def _specimen_fact(
    spm: list[str],
    path: str,
    *,
    patient_id: str,
    observation_ids: list[str],
    lifted_id: str,
) -> LiftedFact:
    identifier = _identifier_from_ei(_field(spm, 2))
    relationships = [
        ("specimen_for_observation", observation_id)
        for observation_id in observation_ids
    ]
    effective = _ts_to_iso(_field(spm, 17))
    payload = {
        "fact_type": "specimen",
        "subject_ref": patient_id,
        "encounter_ref": None,
        "concept": None,
        "value": None,
        "unit": None,
        "temporal": {
            "effective_start": effective,
            "effective_end": None,
            "recorded_at": None,
            "precision": "second" if effective else None,
        },
        "identifiers": [identifier] if identifier is not None else [],
        "relations": [
            {"relation_type": relation_type, "target_fact_id": target_id}
            for relation_type, target_id in relationships
        ],
        "attributes": {
            "type_label": _component(_field(spm, 4), 1),
            "collection_method_label": _component(_field(spm, 7), 1),
        },
    }
    return LiftedFact(
        lifted_fact_id=lifted_id,
        fact_type="specimen",
        subject_ref=patient_id,
        semantic_payload=payload,
        target_paths=(path,),
        relationships=tuple(relationships),
    )


class Hl7V251OruLifter:
    """Lift the in-scope v2.5.1 ORU^R01 laboratory slice into candidates."""

    @property
    def lifter_id(self) -> str:
        return _LIFTER_ID

    @property
    def lifter_version(self) -> str:
        return _LIFTER_VERSION

    def lift(
        self,
        artifact: str | dict[str, Any],
        *,
        artifact_id: str,
    ) -> LiftResult:
        if not isinstance(artifact, str):
            raise TypeError("HL7 v2 lifter requires ER7 text")
        segments = _parse_segments(artifact)
        if not segments or segments[0][0] != "MSH":
            raise ValueError("HL7 v2 artifact must begin with MSH")
        message_type = _field(segments[0], 8)
        version = _field(segments[0], 11)
        if not message_type.startswith("ORU^R01"):
            raise ValueError("HL7 v2 lab lifter currently requires ORU^R01")
        if version != "2.5.1":
            raise ValueError("HL7 v2 lab lifter currently requires version 2.5.1")

        warnings: list[LiftWarning] = []
        pid_items = _segment_index(segments, "PID")
        obr_items = _segment_index(segments, "OBR")
        if len(pid_items) != 1 or not obr_items:
            raise ValueError(
                "development ORU slice requires exactly one PID and at least one OBR"
            )

        patient = _patient_fact(pid_items[0][1], f"PID[{pid_items[0][0]}]")
        facts: list[LiftedFact] = [patient]
        all_orders: list[LiftedFact] = []
        all_observations: list[LiftedFact] = []
        all_specimens: list[LiftedFact] = []

        obr_positions = [index for index, _ in obr_items]
        for group_number, (obr_index, obr) in enumerate(obr_items, start=1):
            next_obr_index = (
                obr_positions[group_number]
                if group_number < len(obr_positions)
                else len(segments)
            )
            report_id = f"v2::report::{group_number}"
            previous_obr_index = (
                obr_positions[group_number - 2] if group_number > 1 else pid_items[0][0]
            )
            preceding_orc: tuple[int, list[str]] | None = next(
                (
                    (index, segments[index])
                    for index in range(obr_index - 1, previous_obr_index, -1)
                    if segments[index][0] == "ORC"
                ),
                None,
            )
            order_id = (
                f"v2::order::{group_number}"
                if preceding_orc is not None
                or _field(obr, 2)
                or _field(obr, 3)
                or _field(obr, 16)
                else None
            )
            group_segments = [
                (index, segments[index])
                for index in range(obr_index + 1, next_obr_index)
            ]

            specimen_entries: list[tuple[int, list[str], str]] = []
            raw_result_observations: list[tuple[int, list[str], str]] = []
            used_observation_ids: set[str] = set()
            used_specimen_ids: set[str] = set()
            spm_counter = 0
            obx_counter = 0
            specimen_group_started = False

            for segment_index, segment in group_segments:
                if segment[0] == "SPM":
                    specimen_group_started = True
                    spm_counter += 1
                    token = _field(segment, 1) or str(spm_counter)
                    specimen_id = (
                        f"v2::spm::{token}"
                        if len(obr_items) == 1
                        else f"{report_id}::spm::{token}"
                    )
                    if specimen_id in used_specimen_ids:
                        specimen_id = f"{specimen_id}::{spm_counter}"
                    used_specimen_ids.add(specimen_id)
                    specimen_entries.append(
                        (segment_index, segment, specimen_id)
                    )
                elif segment[0] == "OBX":
                    if specimen_group_started:
                        warnings.append(
                            LiftWarning(
                                code="SPECIMEN_OBX_OUTSIDE_RESULT_SLICE",
                                message=(
                                    "OBX after SPM belongs to the specimen group and "
                                    "is not lifted as a report-result observation."
                                ),
                                target_paths=(f"OBX[{segment_index}]",),
                            )
                        )
                        continue
                    obx_counter += 1
                    token = _field(segment, 1) or str(obx_counter)
                    observation_id = (
                        f"v2::obx::{token}"
                        if len(obr_items) == 1
                        else f"{report_id}::obx::{token}"
                    )
                    if observation_id in used_observation_ids:
                        observation_id = f"{observation_id}::{obx_counter}"
                    used_observation_ids.add(observation_id)
                    raw_result_observations.append(
                        (segment_index, segment, observation_id)
                    )

            # In the current bounded benchmark slice an ORDER_OBSERVATION has
            # at most one source specimen. With exactly one SPM, that specimen
            # is the source specimen context for each result OBX in the same
            # OBR group. Multiple SPMs are intentionally left un-attributed
            # rather than guessed.
            inferred_specimen_id = (
                specimen_entries[0][2] if len(specimen_entries) == 1 else None
            )
            if len(specimen_entries) > 1 and raw_result_observations:
                warnings.append(
                    LiftWarning(
                        code="MULTIPLE_SPECIMENS_RESULT_LINK_INDETERMINATE",
                        message=(
                            "Multiple SPM segments prevent deterministic specimen "
                            "attribution for result OBXs in the bounded lifter."
                        ),
                        target_paths=(f"OBR[{obr_index}]",),
                    )
                )
            observation_entries: list[
                tuple[int, list[str], str, str | None]
            ] = [
                (segment_index, segment, observation_id, inferred_specimen_id)
                for segment_index, segment, observation_id
                in raw_result_observations
            ]

            observation_ids = [
                observation_id
                for _, _, observation_id, _ in observation_entries
            ]
            specimen_ids = [
                specimen_id
                for _, _, specimen_id in specimen_entries
            ]
            report = _report_fact(
                obr,
                f"OBR[{obr_index}]",
                patient_id=patient.lifted_fact_id,
                report_id=report_id,
                observation_ids=observation_ids,
                specimen_ids=specimen_ids,
                order_id=order_id,
            )
            facts.append(report)

            if order_id is not None:
                orc_index = preceding_orc[0] if preceding_orc is not None else None
                orc_segment = preceding_orc[1] if preceding_orc is not None else None
                order = _order_fact(
                    orc_segment,
                    obr,
                    orc_path=f"ORC[{orc_index}]" if orc_index is not None else None,
                    obr_path=f"OBR[{obr_index}]",
                    patient_id=patient.lifted_fact_id,
                    report_id=report_id,
                    lifted_id=order_id,
                )
                if order is not None:
                    all_orders.append(order)

            group_observations = [
                _observation_fact(
                    segment,
                    f"OBX[{segment_index}]",
                    patient_id=patient.lifted_fact_id,
                    report_id=report_id,
                    specimen_id=specimen_id,
                    lifted_id=observation_id,
                )
                for (
                    segment_index,
                    segment,
                    observation_id,
                    specimen_id,
                ) in observation_entries
            ]
            all_observations.extend(group_observations)

            for segment_index, segment, specimen_id in specimen_entries:
                linked_observation_ids = [
                    observation_id
                    for _, _, observation_id, linked_specimen_id
                    in observation_entries
                    if linked_specimen_id == specimen_id
                ]
                all_specimens.append(
                    _specimen_fact(
                        segment,
                        f"SPM[{segment_index}]",
                        patient_id=patient.lifted_fact_id,
                        observation_ids=linked_observation_ids,
                        lifted_id=specimen_id,
                    )
                )

        facts.extend(all_orders)
        facts.extend(all_specimens)
        facts.extend(all_observations)

        known = {"MSH", "PID", "ORC", "OBR", "OBX", "SPM"}
        for index, segment in enumerate(segments):
            if segment[0] not in known:
                warnings.append(
                    LiftWarning(
                        code="UNLIFTED_SEGMENT",
                        message=f"Segment {segment[0]} is outside the development slice.",
                        target_paths=(f"segment[{index}]",),
                    )
                )

        return LiftResult(
            artifact_id=artifact_id,
            lifter_id=self.lifter_id,
            lifter_version=self.lifter_version,
            source_standard="HL7_v2.5.1",
            source_profile="LRI_Edition_5_ORU_R01_development_slice",
            facts=tuple(facts),
            warnings=tuple(warnings),
            metadata={
                "message_type": message_type,
                "version": version,
                "observation_count": len(all_observations),
                "order_count": len(all_orders),
                "report_count": len(obr_items),
                "specimen_count": len(all_specimens),
                "semantic_verdict_emitted": False,
            },
        )
