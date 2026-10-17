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



def _lines(artifact: str) -> list[str]:
    return [line for line in artifact.replace("\n", "\r").split("\r") if line]


def _group_bounds(lines: list[str]) -> list[tuple[int, int]]:
    obr_indexes = [index for index, line in enumerate(lines) if line.startswith("OBR|")]
    return [
        (
            start,
            obr_indexes[position + 1]
            if position + 1 < len(obr_indexes)
            else len(lines),
        )
        for position, start in enumerate(obr_indexes)
    ]


def misattribute_observation_to_report(
    artifact: str,
    *,
    source_group: int = 0,
    target_group: int = 1,
    observation_occurrence: int = 0,
) -> ArtifactMutation:
    """F007: move one intact OBX into the wrong OBR group.

    The operator preserves the OBX payload and only changes report-group
    membership. Qualification fixtures should avoid specimen context unless the
    specimen is intentionally part of the same fault.
    """

    lines = _lines(artifact)
    groups = _group_bounds(lines)
    if source_group == target_group:
        raise ValueError("source_group and target_group must differ")
    if source_group < 0 or source_group >= len(groups):
        raise ValueError("source report group not found")
    if target_group < 0 or target_group >= len(groups):
        raise ValueError("target report group not found")

    source_start, source_end = groups[source_group]
    source_obx_indexes = [
        index
        for index in range(source_start + 1, source_end)
        if lines[index].startswith("OBX|")
    ]
    if observation_occurrence < 0 or observation_occurrence >= len(source_obx_indexes):
        raise ValueError("source observation occurrence not found")

    moved_index = source_obx_indexes[observation_occurrence]
    moved = lines.pop(moved_index)

    # Recompute group boundaries after removal before choosing insertion point.
    groups = _group_bounds(lines)
    _, target_end = groups[target_group]
    lines.insert(target_end, moved)

    return ArtifactMutation(
        artifact="\r".join(lines) + "\r",
        fault_id="F007",
        expected_classification="MISATTRIBUTION",
        expected_severity="S3",
        structural_validity_expected=True,
        target_path=(
            f"ORU_ORDER_OBSERVATION[{source_group}]"
            f"->ORU_ORDER_OBSERVATION[{target_group}]"
        ),
        description=(
            "An otherwise intact observation was moved from its source OBR group "
            "into a different report group."
        ),
    )


def swap_specimen_identifiers(
    artifact: str,
    *,
    first_occurrence: int = 0,
    second_occurrence: int = 1,
) -> ArtifactMutation:
    """F014: swap SPM-2 across distinct single-specimen report/result contexts."""

    if first_occurrence == second_occurrence:
        raise ValueError("specimen occurrences must differ")
    lines = _lines(artifact)
    spm_indexes = [
        index for index, line in enumerate(lines) if line.startswith("SPM|")
    ]
    if (
        first_occurrence < 0
        or second_occurrence < 0
        or first_occurrence >= len(spm_indexes)
        or second_occurrence >= len(spm_indexes)
    ):
        raise ValueError("two specimen occurrences are required")

    first_index = spm_indexes[first_occurrence]
    second_index = spm_indexes[second_occurrence]

    # This operator models a *cross-context* semantic attribution error,
    # not an arbitrary exchange of two string fields in one report. Require
    # two different OBR/result groups, each with exactly one associated SPM
    # and at least one observation, before assigning an expected error label.
    # Synthetic stimuli failing these preconditions are rejected, never
    # treated as successfully qualified misattribution examples.
    groups = _group_bounds(lines)
    if len(groups) < 2:
        raise ValueError("F014 requires at least two distinct OBR/result contexts")

    selected_groups: list[int] = []
    for selected in (first_index, second_index):
        belonging = [
            group_idx
            for group_idx, (start, end) in enumerate(groups)
            if start < selected < end
        ]
        if len(belonging) != 1:
            raise ValueError("selected SPM must belong to exactly one OBR group")
        group_idx = belonging[0]
        start, end = groups[group_idx]
        group_lines = lines[start + 1:end]
        if sum(item.startswith("SPM|") for item in group_lines) != 1:
            raise ValueError("F014 requires a unique SPM within each selected report group")
        # This repository's supported ORU group shape places results
        # BEFORE SPM. An OBX that appears after this SPM is rejected by
        # the development structural validator and not lifted into the
        # same result slice, so it cannot ground an F014 misattribution.
        if not any(
            lines[index].startswith("OBX|")
            for index in range(start + 1, selected)
        ):
            raise ValueError("F014 requires an OBX result before each selected SPM")
        selected_groups.append(group_idx)
    if selected_groups[0] == selected_groups[1]:
        raise ValueError("F014 selected specimens must belong to different OBR groups")

    first = lines[first_index].split("|")
    second = lines[second_index].split("|")
    while len(first) <= 2:
        first.append("")
    while len(second) <= 2:
        second.append("")
    if not first[2] or not second[2]:
        raise ValueError("both specimen identifiers must be populated")

    def lifted_ei_identity(raw: str) -> tuple[str, str | None]:
        # The current independent SPM lifter scores EI-1 value and EI-2
        # namespace. Empty trailing EI components are not independent
        # specimen facts in that scored representation. A byte-only change
        # must not be sold as a successful clinical misattribution mutant.
        components = raw.split("^")
        value = components[0]
        namespace = components[1] if len(components) > 1 and components[1] else None
        if not value:
            raise ValueError("F014 requires a populated SPM-2 EI identifier value")
        return (value, namespace)

    if lifted_ei_identity(first[2]) == lifted_ei_identity(second[2]):
        raise ValueError(
            "F014 would be a no-op under the current specimen-lifter identity"
        )
    first[2], second[2] = second[2], first[2]
    lines[first_index] = "|".join(first)
    lines[second_index] = "|".join(second)

    return ArtifactMutation(
        artifact="\r".join(lines) + "\r",
        fault_id="F014",
        expected_classification="MISATTRIBUTION",
        expected_severity="S3",
        structural_validity_expected=True,
        target_path=(
            f"SPM[{first_occurrence}]-2<->SPM[{second_occurrence}]-2"
        ),
        description=(
            "Two valid specimen identifiers were exchanged between otherwise "
            "unchanged specimen/result contexts."
        ),
    )

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
