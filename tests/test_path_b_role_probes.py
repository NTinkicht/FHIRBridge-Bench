"""Synthetic role/locus anti-conflation controls, never Edition 5 G1 gold."""

import pytest

from fhirbridge.path_b_order_diagnostics import inspect_order_context_candidate
from fhirbridge.path_b_role_probes import (
    AuthoredIdentifierRoles,
    inspect_authored_identifier_loci,
)

SOURCE = AuthoredIdentifierRoles(
    accession="ACC-900^ACC-AUTH",
    placer="PLC-100^PLACER-AUTH",
    filler="FIL-200^FILLER-AUTH",
    service_request_code="1111-1^Order^LN",
    diagnostic_report_code="2222-2^Report^LN",
)
EXPECTED = {
    "ORC-2": "placer",
    "ORC-3": "filler",
    "OBR-2": "placer",
    "OBR-3": "filler",
}


def _seg(name: str, values: dict[int, str]) -> str:
    fields = [""] * max(values)
    for field_number, value in values.items():
        fields[field_number - 1] = value
    return name + "|" + "|".join(fields)


def _message(
    *,
    orc_placer: str = SOURCE.placer,
    obr_placer: str = SOURCE.placer,
    orc_filler: str = SOURCE.filler,
    obr_filler: str = SOURCE.filler,
) -> str:
    return "\r".join(
        [
            "MSH|^~\\&|DEV|ONLY|DEV|ONLY|20261016010000||ORU^R01|1|P|2.5.1",
            "PID|1||SYNTHETIC-1",
            _seg(
                "ORC",
                {
                    1: "RE",
                    2: orc_placer,
                    3: orc_filler,
                    12: "P-1^Clinician",
                },
            ),
            _seg(
                "OBR",
                {
                    1: "1",
                    2: obr_placer,
                    3: obr_filler,
                    4: SOURCE.diagnostic_report_code,
                    16: "P-1^Clinician",
                },
            ),
            "OBX|1|NM|123^Synthetic^LN||5|mg/dL",
            "",
        ]
    )


def _probe(message: str):
    return inspect_authored_identifier_loci(
        message,
        source=SOURCE,
        fixture_expected_loci=EXPECTED,
    )


def test_synthetic_matching_loci_never_promote_g1_or_semantics() -> None:
    probe = _probe(_message())
    assert probe.mismatched_loci == ()
    assert len(probe.loci) == 4
    assert all(item.matches_fixture_expectation for item in probe.loci)
    assert probe.status == "PREFREEZE_FIXTURE_ASSERTIONS_ONLY"
    assert probe.semantic_verdict == "INDETERMINATE"
    assert probe.G1_qualified is False
    assert probe.primary_endpoint_eligible is False
    assert (
        probe.order_code_observation
        == "DISTINCT_SERVICE_REQUEST_AND_REPORT_CODES_UNRESOLVED"
    )


def test_role_swap_in_both_mirrors_is_detected_despite_candidate_clean() -> None:
    artifact = _message(
        orc_placer=SOURCE.filler,
        obr_placer=SOURCE.filler,
        orc_filler=SOURCE.placer,
        obr_filler=SOURCE.placer,
    )
    # Cross-field equality alone incorrectly appears reassuring.
    assert inspect_order_context_candidate(artifact).candidate_error_codes == set()
    probe = _probe(artifact)
    assert set(probe.mismatched_loci) == set(EXPECTED)
    assert all(item.source_grounded is True for item in probe.loci)
    assert {item.observation for item in probe.loci} == {
        "OTHER_SOURCE_AUTHORED_ROLE"
    }
    assert probe.semantic_verdict == "INDETERMINATE"


@pytest.mark.parametrize("field", ["placer", "filler"])
def test_source_authored_accession_is_not_automatically_order_identifier(
    field: str,
) -> None:
    changes = (
        {"orc_placer": SOURCE.accession, "obr_placer": SOURCE.accession}
        if field == "placer"
        else {"orc_filler": SOURCE.accession, "obr_filler": SOURCE.accession}
    )
    artifact = _message(**changes)
    assert inspect_order_context_candidate(artifact).candidate_error_codes == set()
    probe = _probe(artifact)
    for item in probe.loci:
        if item.fixture_expected_role == field:
            assert item.source_grounded is True
            assert item.observed_authored_role == "accession"
            assert item.matches_fixture_expectation is False
            assert item.observation == "OTHER_SOURCE_AUTHORED_ROLE"
    assert probe.G1_qualified is False


@pytest.mark.parametrize("field", ["placer", "filler"])
def test_fabricated_identifier_detected_as_not_authored_without_semantic_label(
    field: str,
) -> None:
    changes = (
        {"orc_placer": "MADE-UP^LAB", "obr_placer": "MADE-UP^LAB"}
        if field == "placer"
        else {"orc_filler": "MADE-UP^LAB", "obr_filler": "MADE-UP^LAB"}
    )
    probe = _probe(_message(**changes))
    involved = [item for item in probe.loci if item.fixture_expected_role == field]
    assert len(involved) == 2
    assert all(item.source_grounded is False for item in involved)
    assert all(item.observation == "NOT_SOURCE_AUTHORED" for item in involved)
    assert probe.semantic_verdict == "INDETERMINATE"


def test_missing_placer_is_observed_without_asserting_normative_requirement() -> None:
    probe = _probe(_message(orc_placer=""))
    item = next(item for item in probe.loci if item.locus == "ORC-2")
    assert item.observation == "ABSENT"
    assert item.source_grounded is None
    assert not item.matches_fixture_expectation
    assert probe.mismatched_loci == ("ORC-2",)


def test_partial_placer_mirror_is_not_silently_promoted() -> None:
    result = inspect_order_context_candidate(_message(orc_placer=""))
    assert any(item.review_required for item in result.findings)
    assert not _probe(_message(orc_placer="")).G1_qualified


@pytest.mark.parametrize(
    "loci",
    [
        {},
        {"ORC-2": "placer"},
        {**EXPECTED, "MSH-21": "filler"},
        {**EXPECTED, "ORC-2": "accession"},
    ],
)
def test_ambiguous_or_incomplete_fixture_expectations_fail_closed(
    loci: dict[str, str],
) -> None:
    with pytest.raises(ValueError, match="loci|roles|allowed"):
        inspect_authored_identifier_loci(
            _message(), source=SOURCE, fixture_expected_loci=loci
        )


def test_duplicate_roles_cannot_hide_an_identifier_role_swap() -> None:
    with pytest.raises(ValueError, match="distinct"):
        AuthoredIdentifierRoles(
            accession=SOURCE.filler,
            placer=SOURCE.placer,
            filler=SOURCE.filler,
            service_request_code=SOURCE.service_request_code,
            diagnostic_report_code=SOURCE.diagnostic_report_code,
        )


def test_multiple_obr_groups_fail_closed_in_single_group_probe() -> None:
    message = _message() + _seg("OBR", {1: "2", 3: SOURCE.filler}) + "\r"
    with pytest.raises(ValueError, match="exactly one ORC and one OBR"):
        _probe(message)


def test_orc_before_pid_cannot_launder_an_order_identifier() -> None:
    segments = [part for part in _message().split("\r") if part]
    orc = next(part for part in segments if part.startswith("ORC|"))
    segments.remove(orc)
    segments.insert(1, orc)
    with pytest.raises(ValueError, match="PID before"):
        _probe("\r".join(segments) + "\r")
