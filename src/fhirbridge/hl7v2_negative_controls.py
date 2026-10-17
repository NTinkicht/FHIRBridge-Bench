"""Deterministic HL7 v2 structural-negative controls for profile qualification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hl7NegativeControl:
    control_id: str
    description: str
    artifact: str
    expected_structural_error: bool = True
    expected_error_location_tokens: tuple[str, ...] = ()


def _segments(message: str) -> list[str]:
    normalized = message.replace("\r\n", "\r").replace("\n", "\r")
    return [segment for segment in normalized.split("\r") if segment]


def _serialize(segments: list[str]) -> str:
    return "\r".join(segments) + "\r"


def _replace_msh_field(message: str, field_number: int, value: str) -> str:
    segments = _segments(message)
    if not segments or not segments[0].startswith("MSH|"):
        raise ValueError("message must begin with MSH")
    fields = segments[0].split("|")
    # MSH-1 is the separator itself, so split indexes align from MSH-2 onward:
    # index 8 -> MSH-9, index 11 -> MSH-12.
    index = field_number - 1
    if index >= len(fields):
        raise ValueError(f"MSH-{field_number} is not present")
    fields[index] = value
    segments[0] = "|".join(fields)
    return _serialize(segments)


def _drop_segment(message: str, segment_name: str) -> str:
    segments = _segments(message)
    retained = [
        segment
        for segment in segments
        if segment.split("|", 1)[0] != segment_name
    ]
    if len(retained) == len(segments):
        raise ValueError(f"segment {segment_name} was not present")
    return _serialize(retained)


def build_structural_negative_controls(message: str) -> tuple[Hl7NegativeControl, ...]:
    """Create profile-independent high-confidence negative controls.

    These controls target message identity and required patient context, not
    disputed LRI Edition 5 order semantics. ORC/OBR-specific negatives are added
    only after the exact Edition 5 profile has been acquired and reviewed.
    """

    return (
        Hl7NegativeControl(
            control_id="NEG-HL7-VERSION",
            description="Change MSH-12 from 2.5.1 to 2.3.1.",
            artifact=_replace_msh_field(message, 12, "2.3.1"),
            expected_error_location_tokens=("MSH", "12"),
        ),
        Hl7NegativeControl(
            control_id="NEG-MESSAGE-STRUCTURE",
            description="Change MSH-9 to a non-ORU message identity.",
            artifact=_replace_msh_field(message, 9, "ADT^A01^ADT_A01"),
            expected_error_location_tokens=("MSH", "9"),
        ),
        Hl7NegativeControl(
            control_id="NEG-MISSING-PID",
            description="Remove the PID segment from the patient-result message.",
            artifact=_drop_segment(message, "PID"),
            expected_error_location_tokens=("PID",),
        ),
    )
