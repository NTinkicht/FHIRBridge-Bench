"""Target-artifact semantic and structural fault injection for HL7 v2 ER7.

Some interoperability faults do not survive canonical re-rendering because the
target standard carries context at message/group level rather than on each
clinical fact. These operators therefore mutate the serialized target artifact
itself. They remain independent of verifier decision code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactMutation:
    artifact: str
    fault_id: str
    expected_classification: str
    expected_severity: str
    structural_validity_expected: bool
    target_path: str
    description: str


def _mutate_field(
    artifact: str,
    *,
    segment_name: str,
    field_number: int,
    value: str,
    occurrence: int = 0,
) -> str:
    output: list[str] = []
    seen = 0
    mutated = False
    for line in artifact.replace("\n", "\r").split("\r"):
        if not line:
            continue
        fields = line.split("|")
        if fields[0] == segment_name:
            if seen == occurrence:
                while len(fields) <= field_number:
                    fields.append("")
                fields[field_number] = value
                mutated = True
            seen += 1
        output.append("|".join(fields))
    if not mutated:
        raise ValueError(
            f"segment occurrence not found: {segment_name}[{occurrence}]"
        )
    return "\r".join(output) + "\r"


def omit_report_issued_time(artifact: str) -> ArtifactMutation:
    """F009: remove OBR-22 while leaving the message parseable."""

    mutated = _mutate_field(
        artifact,
        segment_name="OBR",
        field_number=22,
        value="",
    )
    return ArtifactMutation(
        artifact=mutated,
        fault_id="F009",
        expected_classification="OMISSION",
        expected_severity="S2",
        structural_validity_expected=True,
        target_path="OBR-22",
        description="Required report issued time removed from an otherwise parseable ORU.",
    )


def add_unauthorized_derived_observation(artifact: str) -> ArtifactMutation:
    """F016: append a plausible but unsupported derived clinical assertion."""

    lines = [line for line in artifact.replace("\n", "\r").split("\r") if line]
    obx_count = sum(1 for line in lines if line.startswith("OBX|"))
    set_id = obx_count + 1
    unsupported = (
        f"OBX|{set_id}|ST|FHIRBRIDGE-RISK^Derived metabolic risk^99FBR|"
        "|high||||||F"
    )
    insert_after = max(
        (index for index, line in enumerate(lines) if line.startswith("OBX|")),
        default=len(lines) - 1,
    )
    lines.insert(insert_after + 1, unsupported)
    return ArtifactMutation(
        artifact="\r".join(lines) + "\r",
        fault_id="F016",
        expected_classification="FABRICATION",
        expected_severity="S2",
        structural_validity_expected=True,
        target_path=f"OBX[{set_id}]",
        description=(
            "Unsupported derived risk assertion added without source grounding or "
            "contract-licensed derivation."
        ),
    )


def corrupt_message_version(artifact: str) -> ArtifactMutation:
    """F018: syntax/profile negative control that must fail the structural gate."""

    mutated = _mutate_field(
        artifact,
        segment_name="MSH",
        field_number=11,
        value="INVALID",
    )
    return ArtifactMutation(
        artifact=mutated,
        fault_id="F018",
        expected_classification="STRUCTURAL_ERROR",
        expected_severity="S1",
        structural_validity_expected=False,
        target_path="MSH-12",
        description="Message version replaced with an invalid value.",
    )
