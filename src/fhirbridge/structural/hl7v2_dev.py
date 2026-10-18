"""Development structural sanity gate for the bounded v2.5.1 ORU^R01 slice.

This is deliberately *not* represented as LRI Edition 5 conformance testing.
It catches malformed/out-of-slice artifacts during development while an
independent profile-level validator is integrated for confirmatory experiments.
"""

from __future__ import annotations

import re

from .base import StructuralFinding, StructuralValidationResult

_VALIDATOR_ID = "hl7v251-oru-development-structural-gate"
_VALIDATOR_VERSION = "0.3.0-dev"
_PROFILE = "HL7_v2.5.1_ORU_R01_development_slice_not_LRI_certification"
_TS = re.compile(r"^\d{8}(?:\d{6}(?:[+-]\d{4})?)?$")


def _segments(artifact: str) -> list[list[str]]:
    normalized = artifact.replace("\n", "\r")
    return [segment.split("|") for segment in normalized.split("\r") if segment]


def _field(segment: list[str], number: int) -> str:
    return segment[number] if number < len(segment) else ""


def _finding(code: str, message: str, path: str | None = None) -> StructuralFinding:
    return StructuralFinding(code=code, message=message, severity="error", path=path)


class Hl7V251OruDevelopmentValidator:
    """Check syntax/profile-shape prerequisites without making semantic claims."""

    @property
    def validator_id(self) -> str:
        return _VALIDATOR_ID

    @property
    def validator_version(self) -> str:
        return _VALIDATOR_VERSION

    def validate(self, artifact: str) -> StructuralValidationResult:
        findings: list[StructuralFinding] = []
        segments = _segments(artifact)
        if not segments:
            findings.append(_finding("EMPTY_MESSAGE", "Artifact contains no HL7 segments."))
            return self._result(findings, 0)

        if segments[0][0] != "MSH":
            findings.append(
                _finding("MSH_NOT_FIRST", "First segment must be MSH.", "segment[0]")
            )
            return self._result(findings, len(segments))

        msh = segments[0]
        message_type = _field(msh, 8)
        version = _field(msh, 11)
        if not message_type.startswith("ORU^R01"):
            findings.append(
                _finding(
                    "WRONG_MESSAGE_TYPE",
                    f"Expected ORU^R01, found {message_type or '<empty>'}.",
                    "MSH-9",
                )
            )
        if version != "2.5.1":
            findings.append(
                _finding(
                    "WRONG_VERSION",
                    f"Expected 2.5.1, found {version or '<empty>'}.",
                    "MSH-12",
                )
            )

        named = [segment[0] for segment in segments]
        for required in ("PID", "OBR", "OBX"):
            count = named.count(required)
            if count == 0:
                findings.append(
                    _finding(
                        f"MISSING_{required}",
                        f"Development slice requires at least one {required} segment.",
                    )
                )
        if named.count("PID") > 1:
            findings.append(
                _finding(
                    "MULTIPLE_PID",
                    "Development slice currently supports exactly one PID.",
                )
            )
        obr_indexes = [
            index for index, segment in enumerate(segments) if segment[0] == "OBR"
        ]
        if obr_indexes:
            first_obr = obr_indexes[0]
            for index, segment in enumerate(segments[:first_obr]):
                if segment[0] in {"SPM", "OBX"}:
                    findings.append(
                        _finding(
                            "RESULT_SEGMENT_BEFORE_OBR",
                            f"{segment[0]} must belong to an OBR group.",
                            f"segment[{index}]",
                        )
                    )
            for group_number, start in enumerate(obr_indexes, start=1):
                end = (
                    obr_indexes[group_number]
                    if group_number < len(obr_indexes)
                    else len(segments)
                )
                if not any(
                    segment[0] == "OBX" for segment in segments[start + 1 : end]
                ):
                    findings.append(
                        _finding(
                            "OBR_GROUP_WITHOUT_OBX",
                            "Each development OBR group requires at least one OBX.",
                            f"OBR[{start}]",
                        )
                    )
                # The benchmark result slice does not use specimen-observation
                # OBXs. Once SPM begins, a later OBX is therefore not a report
                # result and indicates the old renderer/lifter grouping error.
                spm_seen = False
                for index in range(start + 1, end):
                    segment = segments[index]
                    if segment[0] == "SPM":
                        spm_seen = True
                    elif segment[0] == "OBX" and spm_seen:
                        findings.append(
                            _finding(
                                "RESULT_OBX_AFTER_SPM",
                                (
                                    "Result-slice OBX must precede SPM; OBX after "
                                    "SPM belongs to the specimen-observation group."
                                ),
                                f"segment[{index}]",
                            )
                        )

        for index, segment in enumerate(segments):
            name = segment[0]
            if name == "PID" and not _field(segment, 3):
                findings.append(
                    _finding(
                        "PID3_REQUIRED",
                        "PID-3 is required in this slice.",
                        f"PID[{index}]-3",
                    )
                )
            elif name == "OBR":
                if not _field(segment, 4):
                    findings.append(
                        _finding(
                            "OBR4_REQUIRED",
                            "OBR-4 is required in this slice.",
                            f"OBR[{index}]-4",
                        )
                    )
                self._check_ts(findings, _field(segment, 7), f"OBR[{index}]-7")
                self._check_ts(findings, _field(segment, 22), f"OBR[{index}]-22")
            elif name == "OBX":
                for number in (2, 3, 5, 11):
                    if not _field(segment, number):
                        findings.append(
                            _finding(
                                f"OBX{number}_REQUIRED",
                                f"OBX-{number} is required in this development slice.",
                                f"OBX[{index}]-{number}",
                            )
                        )
                self._check_ts(findings, _field(segment, 14), f"OBX[{index}]-14")
            elif name == "SPM":
                if not _field(segment, 2):
                    findings.append(
                        _finding(
                            "SPM2_REQUIRED",
                            "SPM-2 is required when SPM is present.",
                            f"SPM[{index}]-2",
                        )
                    )
                self._check_ts(findings, _field(segment, 17), f"SPM[{index}]-17")
            elif name not in {"MSH", "PID", "OBR", "OBX", "SPM"}:
                findings.append(
                    StructuralFinding(
                        code="OUT_OF_SLICE_SEGMENT",
                        message=f"Segment {name} is outside the development slice.",
                        severity="warning",
                        path=f"segment[{index}]",
                    )
                )

        return self._result(findings, len(segments))

    def _check_ts(
        self,
        findings: list[StructuralFinding],
        value: str,
        path: str,
    ) -> None:
        if value and _TS.fullmatch(value) is None:
            findings.append(
                _finding(
                    "INVALID_TS_SHAPE",
                    f"Timestamp {value!r} is outside the accepted development TS shape.",
                    path,
                )
            )

    def _result(
        self,
        findings: list[StructuralFinding],
        segment_count: int,
    ) -> StructuralValidationResult:
        valid = not any(finding.severity == "error" for finding in findings)
        return StructuralValidationResult(
            valid=valid,
            validator_id=self.validator_id,
            validator_version=self.validator_version,
            profile=_PROFILE,
            findings=tuple(findings),
            metadata={
                "segment_count": segment_count,
                "profile_level_conformance_claimed": False,
            },
        )
