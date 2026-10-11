"""Development-only LRI Edition 5 order diagnostics, not conformance tests."""

import pytest

from fhirbridge.path_b_order_diagnostics import inspect_order_context_candidate


def _seg(name: str, fields: dict[int, str]) -> str:
    maximum = max(fields, default=0)
    parts = [""] * maximum
    for field_number, value in fields.items():
        parts[field_number - 1] = value
    return name + "|" + "|".join(parts)


def _msg(
    *,
    control: str = "RE",
    filler: str = "FILLER-1^LOCAL",
    obr_filler: str = "FILLER-1^LOCAL",
    provider: str = "PROV-1^Clinician",
    obr_provider: str = "PROV-1^Clinician",
    placer: str = "",
    obr_placer: str = "",
    orc: bool = True,
    copies: int = 1,
) -> str:
    segments = [
        "MSH|^~\\&|DEV|ONLY|DEV|ONLY|20261011120000||ORU^R01^ORU_R01|1|P|2.5.1",
        "PID|1||MRN-1",
    ]
    for _ in range(copies):
        if orc:
            segments.append(
                _seg(
                    "ORC",
                    {1: control, 2: placer, 3: filler, 12: provider},
                )
            )
        segments.append(
            _seg(
                "OBR",
                {
                    1: "1",
                    2: obr_placer,
                    3: obr_filler,
                    4: "24323-8^Panel^LN",
                    16: obr_provider,
                },
            )
        )
        segments.append("OBX|1|NM|123^Result^LN||5|mg/dL")
    return "\r".join(segments) + "\r"


def _codes(message: str) -> set[str]:
    return inspect_order_context_candidate(message).candidate_error_codes


def test_clean_candidate_is_never_representation_of_g1_qualification() -> None:
    result = inspect_order_context_candidate(_msg())
    assert result.findings == ()
    assert result.checked_order_groups == 1
    assert result.status == "PREFREEZE_CANDIDATE_ONLY"
    assert result.G1_qualified is False


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"orc": False}, "ORC_CARDINALITY"),
        ({"control": ""}, "ORC1_REQUIRED"),
        ({"filler": ""}, "ORC3_REQUIRED"),
        ({"obr_filler": ""}, "OBR3_REQUIRED"),
        ({"provider": ""}, "ORC12_REQUIRED"),
        ({"obr_provider": ""}, "OBR16_REQUIRED"),
        ({"obr_filler": "WRONG^LOCAL"}, "FILLER_ORDER_MISMATCH"),
        ({"obr_provider": "WRONG^PROVIDER"}, "ORDERING_PROVIDER_MISMATCH"),
        ({"placer": "PLACER-A", "obr_placer": "PLACER-B"}, "PLACER_ORDER_MISMATCH"),
    ],
)
def test_expected_locus_order_negatives(changes: dict, expected: str) -> None:
    result = inspect_order_context_candidate(_msg(**changes))
    assert expected in result.candidate_error_codes
    assert all(f.source_pages for f in result.findings)
    assert result.G1_qualified is False


def test_single_placer_assertion_is_explicitly_for_review_not_invalid_or_valid() -> None:
    result = inspect_order_context_candidate(_msg(placer="PLACER-A"))
    review = [item for item in result.findings if item.review_required]
    assert [item.code for item in review] == [
        "PLACER_MIRROR_REQUIREMENT_UNRESOLVED"
    ]
    assert "PLACER_MIRROR_REQUIREMENT_UNRESOLVED" not in result.candidate_error_codes
    assert result.G1_qualified is False


def test_missing_obr_does_not_return_conformance_pass() -> None:
    result = inspect_order_context_candidate(
        "MSH|^~\\&|DEV|ONLY|DEV|ONLY|20261011120000||ORU^R01|1|P|2.5.1\r"
    )
    assert "OBR_REQUIRED" in result.candidate_error_codes
    assert result.checked_order_groups == 0
    assert result.G1_qualified is False


def test_order_checks_cover_multiple_groups_without_using_renderer_a() -> None:
    result = inspect_order_context_candidate(_msg(copies=2))
    assert result.checked_order_groups == 2
    assert result.candidate_error_codes == set()
    assert result.G1_qualified is False


def test_orc_before_patient_group_cannot_satisfy_current_obr() -> None:
    segments = [segment for segment in _msg(orc=False).split("\r") if segment]
    segments.insert(1, _seg("ORC", {1: "RE", 3: "FILLER-1^LOCAL", 12: "PROV-1^Clinician"}))
    artifact = "\r".join(segments) + "\r"

    result = inspect_order_context_candidate(artifact)

    assert "ORC_CARDINALITY" in result.candidate_error_codes
    assert result.G1_qualified is False


def test_orc_from_previous_patient_cannot_fill_next_group() -> None:
    first = _msg().rstrip("\r")
    second = _msg(orc=False).split("\r")
    later_patient_group = [
        segment
        for segment in second
        if segment.startswith(("PID|", "OBR|", "OBX|"))
    ]
    artifact = first + "\r" + "\r".join(later_patient_group) + "\r"

    result = inspect_order_context_candidate(artifact)

    assert result.checked_order_groups == 2
    assert any(
        finding.code == "ORC_CARDINALITY"
        and finding.locus == "ORDER_OBSERVATION[2]/ORC"
        for finding in result.findings
    )
