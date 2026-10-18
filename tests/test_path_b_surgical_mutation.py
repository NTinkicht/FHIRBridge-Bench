"""One-field control-diff tests are never Edition 5 conformance tests."""

from dataclasses import FrozenInstanceError, replace

import pytest

from fhirbridge.path_b_surgical_mutation import (
    SurgicalMutationEvidence,
    audit_single_field_mutation,
)


def _seg(name: str, fields: dict[int, str]) -> str:
    if name == "MSH":
        values = ["MSH"] + [""] * (max(fields) - 1)
        values[1] = "^~\\&"
        for number, value in fields.items():
            values[number - 1] = value
    else:
        values = [name] + [""] * max(fields)
        for number, value in fields.items():
            values[number] = value
    return "|".join(values)


def _message(
    *,
    version: str = "2.5.1",
    profile: str = "SYNTHETIC.PROFILE.A",
    orc_filler: str = "FILLER-A^AUTH",
    obr_filler: str = "FILLER-A^AUTH",
    obr_code: str = "1111-1^Order^LN",
    obs: str = "5",
) -> str:
    segments = [
        _seg("MSH", {9: "ORU^R01^ORU_R01", 12: version, 21: profile}),
        _seg("PID", {3: "PATIENT-A"}),
        _seg("ORC", {1: "RE", 3: orc_filler}),
        _seg("OBR", {1: "1", 3: obr_filler, 4: obr_code}),
        _seg("OBX", {1: "1", 2: "NM", 3: "123^Test^LN", 5: obs}),
    ]
    return "\r".join(segments) + "\r"


@pytest.mark.parametrize(
    ("after", "locus"),
    [
        ({"version": "2.3.1"}, "MSH-12"),
        ({"profile": "SYNTHETIC.PROFILE.B"}, "MSH-21"),
        ({"orc_filler": "FILLER-B^AUTH"}, "ORC-3"),
        ({"obr_filler": "FILLER-B^AUTH"}, "OBR-3"),
        ({"obr_code": "2222-2^Report^LN"}, "OBR-4"),
        ({"obs": "6"}, "OBX-5"),
    ],
)
def test_single_field_surgical_mutations_are_audited_only(
    after: dict[str, str], locus: str,
) -> None:
    result = audit_single_field_mutation(
        _message(), _message(**after), expected_locus=locus
    )
    assert result.expected_locus == locus
    assert result.observed_locus == locus
    assert result.before_sha256 != result.after_sha256
    assert result.before_value != result.after_value
    assert result.status == "PREFREEZE_SURGICAL_DIFF_ONLY"
    assert result.G1_qualified is False
    assert result.validator_expected_locus_failure_confirmed is False
    assert result.primary_endpoint_eligible is False


def test_relabeling_mutation_cannot_fake_the_expected_locus() -> None:
    with pytest.raises(ValueError, match="unexpected mutated locus: OBR-4"):
        audit_single_field_mutation(
            _message(),
            _message(obr_code="2222-2^Report^LN"),
            expected_locus="OBR-3",
        )


def test_mirrored_identifier_mutation_is_not_single_locus() -> None:
    with pytest.raises(ValueError, match="exactly one HL7 field"):
        audit_single_field_mutation(
            _message(),
            _message(orc_filler="FILLER-B", obr_filler="FILLER-B"),
            expected_locus="OBR-3",
        )


def test_unchanged_control_is_never_accepted_as_negative_evidence() -> None:
    with pytest.raises(ValueError, match="exactly one HL7 field"):
        audit_single_field_mutation(
            _message(), _message(), expected_locus="MSH-21"
        )


def test_segment_drop_fails_before_claiming_field_locus() -> None:
    original = _message()
    changed = "\r".join(
        line for line in original.split("\r") if line and not line.startswith("ORC|")
    ) + "\r"
    with pytest.raises(ValueError, match="segment names/order changed"):
        audit_single_field_mutation(
            original, changed, expected_locus="OBR-3"
        )


def test_added_field_is_not_surgical_mutation() -> None:
    original = _message()
    changed = original.replace("PATIENT-A\r", "PATIENT-A|EXTRA\r")
    with pytest.raises(ValueError, match="field count changed"):
        audit_single_field_mutation(
            original, changed, expected_locus="PID-3"
        )


def test_duplicated_target_segment_is_ambiguous() -> None:
    original = _message()
    parts = [line for line in original.split("\r") if line]
    extra = next(line for line in parts if line.startswith("OBX|"))
    parts.append(extra)
    repeated = "\r".join(parts) + "\r"
    with pytest.raises(ValueError, match="exactly once"):
        audit_single_field_mutation(
            repeated, repeated.replace("|5\r", "|6\r", 1),
            expected_locus="OBX-5",
        )


@pytest.mark.parametrize("locus", ["MSH-1", "OBR-0", "OBR", "MSH-21.1", "ZZZ-"])
def test_unaddressable_or_unsupported_loci_fail_closed(locus: str) -> None:
    with pytest.raises(ValueError, match="expected_locus|MSH-1"):
        audit_single_field_mutation(
            _message(), _message(version="2.3.1"), expected_locus=locus
        )


@pytest.mark.parametrize(
    "bad",
    [
        "MSH|^~\\&\rPID|1",
        "MSH|^~\\&\r\rPID|1\r",
        "PID|1\rMSH|^~\\&\r",
        "MSH|bad\rPID|1\r",
        "",
    ],
)
def test_malformed_artifacts_fail_without_claiming_validation(bad: str) -> None:
    with pytest.raises(ValueError):
        audit_single_field_mutation(
            bad, _message(version="2.3.1"), expected_locus="MSH-12"
        )


def test_cross_pid_group_reordering_is_rejected() -> None:
    source = _message()
    segs = source.split("\r")
    segs[1], segs[2] = segs[2], segs[1]
    with pytest.raises(ValueError, match="segment names/order changed"):
        audit_single_field_mutation(
            source, "\r".join(segs), expected_locus="ORC-3"
        )


def test_same_locus_cr_and_lf_are_only_transport_normalization() -> None:
    result = audit_single_field_mutation(
        _message().replace("\r", "\n"),
        _message(version="2.3.1"),
        expected_locus="MSH-12",
    )
    assert result.observed_locus == "MSH-12"
    assert result.G1_qualified is False


def test_cannot_recast_a_diff_as_g1_qualified() -> None:
    record = audit_single_field_mutation(
        _message(), _message(obr_filler="FILLER-B"), expected_locus="OBR-3"
    )
    # Dataclass is immutable, and callers should not use synthetic diffs as
    # independently validated G1 evidence.
    assert record.G1_qualified is False
    with pytest.raises(FrozenInstanceError):
        record.G1_qualified = True


def test_control_evidence_is_distinct_per_mutant() -> None:
    original = _message()
    one = audit_single_field_mutation(
        original, _message(orc_filler="FILLER-B"), expected_locus="ORC-3"
    )
    two = audit_single_field_mutation(
        original, _message(obr_filler="FILLER-B"), expected_locus="OBR-3"
    )
    assert one.before_sha256 == two.before_sha256
    assert one.after_sha256 != two.after_sha256
    assert replace(one, expected_locus="OBR-3") != two


@pytest.mark.parametrize(
    ("flag", "forged"),
    [
        ("G1_qualified", True),
        ("validator_expected_locus_failure_confirmed", True),
        ("primary_endpoint_eligible", True),
        ("status", "G1_APPROVED"),
    ],
)
def test_constructor_and_replace_cannot_forge_approval(
    flag: str, forged: object,
) -> None:
    original = audit_single_field_mutation(
        _message(), _message(version="2.3.1"), expected_locus="MSH-12"
    )
    payload = {
        "expected_locus": original.expected_locus,
        "observed_locus": original.observed_locus,
        "before_sha256": original.before_sha256,
        "after_sha256": original.after_sha256,
        "before_value": original.before_value,
        "after_value": original.after_value,
        flag: forged,
    }
    with pytest.raises(TypeError):
        SurgicalMutationEvidence(**payload)
    with pytest.raises(TypeError):
        replace(original, **{flag: forged})
