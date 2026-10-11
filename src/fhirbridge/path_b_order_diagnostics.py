"""Development-only, non-normative checks for published LRI Edition 5 order loci.

The rules are candidate interpretations traceable to
benchmark/lri_order_context_evidence.yaml (published Edition 5 pp. 156,
185-190). They have not undergone independent Common+NG+FRU extraction,
adjudication, vocabulary qualification, or original-profile validation.

NEVER use the return value as structural VALID, G1 qualification, or an
input to a confirmatory VUR denominator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateOrderFinding:
    code: str
    locus: str
    source_pages: tuple[int, ...]
    detail: str
    review_required: bool = False


@dataclass(frozen=True)
class CandidateOrderDiagnostics:
    findings: tuple[CandidateOrderFinding, ...]
    checked_order_groups: int
    status: str = "PREFREEZE_CANDIDATE_ONLY"
    G1_qualified: bool = False

    @property
    def candidate_error_codes(self) -> set[str]:
        return {item.code for item in self.findings if not item.review_required}


def _field(segment: list[str], number: int) -> str:
    return segment[number] if len(segment) > number else ""


def inspect_order_context_candidate(artifact: str) -> CandidateOrderDiagnostics:
    """Exercise only page-grounded order requirements; never claim conformance."""

    segments = [
        line.split("|")
        for line in artifact.replace("\r\n", "\r").replace("\n", "\r").split("\r")
        if line.strip()
    ]
    results: list[CandidateOrderFinding] = []

    def note(
        code: str,
        locus: str,
        pages: tuple[int, ...],
        detail: str,
        *,
        review_required: bool = False,
    ) -> None:
        results.append(
            CandidateOrderFinding(
                code=code,
                locus=locus,
                source_pages=pages,
                detail=detail,
                review_required=review_required,
            )
        )

    obr_indices = [
        index for index, segment in enumerate(segments) if segment[0] == "OBR"
    ]
    if not obr_indices:
        note("OBR_REQUIRED", "ORDER_OBSERVATION/OBR", (156,), "Missing OBR group.")
    previous_obr = -1
    for group_number, obr_index in enumerate(obr_indices, start=1):
        obr = segments[obr_index]
        # Do not borrow an ORC from before the current PID or from a
        # previous ORDER_OBSERVATION group. An unrelated earlier ORC cannot
        # satisfy the ORC 1..1 candidate constraint for this OBR.
        last_patient_index = max(
            (
                i
                for i in range(obr_index)
                if segments[i][0] == "PID"
            ),
            default=-1,
        )
        group_start = max(previous_obr, last_patient_index) + 1
        preceding_orcs = [
            s
            for s in segments[group_start:obr_index]
            if s[0] == "ORC"
        ]
        previous_obr = obr_index
        prefix = f"ORDER_OBSERVATION[{group_number}]"

        if len(preceding_orcs) != 1:
            note(
                "ORC_CARDINALITY",
                prefix + "/ORC",
                (156,),
                f"Found {len(preceding_orcs)} ORC segments for this OBR group.",
            )

        for number, pages in ((3, (189,)), (4, (189,)), (16, (190,))):
            if not _field(obr, number):
                note(
                    f"OBR{number}_REQUIRED",
                    f"{prefix}/OBR-{number}",
                    pages,
                    "An explicitly required field is absent.",
                )

        if len(preceding_orcs) != 1:
            continue
        orc = preceding_orcs[0]
        for number, pages in ((1, (185,)), (3, (185,)), (12, (188,))):
            if not _field(orc, number):
                note(
                    f"ORC{number}_REQUIRED",
                    f"{prefix}/ORC-{number}",
                    pages,
                    "An explicitly required field is absent.",
                )

        if _field(orc, 3) and _field(obr, 3) and _field(orc, 3) != _field(obr, 3):
            note(
                "FILLER_ORDER_MISMATCH",
                f"{prefix}/ORC-3=OBR-3",
                (185, 189),
                "The asserted filler order identifiers differ.",
            )
        if _field(orc, 12) and _field(obr, 16) and (
            _field(orc, 12) != _field(obr, 16)
        ):
            note(
                "ORDERING_PROVIDER_MISMATCH",
                f"{prefix}/ORC-12=OBR-16",
                (188, 190),
                "The asserted ordering provider identifiers differ.",
            )

        placer_orc, placer_obr = _field(orc, 2), _field(obr, 2)
        if placer_orc and placer_obr and placer_orc != placer_obr:
            note(
                "PLACER_ORDER_MISMATCH",
                f"{prefix}/ORC-2=OBR-2",
                (185, 189),
                "Both supplied placer order identifiers differ.",
            )
        elif bool(placer_orc) != bool(placer_obr):
            note(
                "PLACER_MIRROR_REQUIREMENT_UNRESOLVED",
                f"{prefix}/ORC-2?OBR-2",
                (185, 189),
                "Only one placer assertion is present; do not infer a pass/fail.",
                review_required=True,
            )

    # These checks omit binding values, coded ORC-1 semantics, MSH-21,
    # optional/conditional fields, EI/XCN components, and full ORU grammar.
    # A clean result is NEVER a G1 conformance pass.
    return CandidateOrderDiagnostics(
        findings=tuple(results),
        checked_order_groups=len(obr_indices),
    )
