"""Synthetic F014 artifact-level misattribution preconditions.

These are controlled development stimuli, not normative Edition 5 validity
or a substitute for blinded verification of the semantic error label.
"""

import pytest

from fhirbridge.artifact_faults import swap_specimen_identifiers


def _message(
    *,
    first_specimen: str = "SPEC-A^LAB",
    second_specimen: str = "SPEC-B^LAB",
    second_observation: bool = True,
) -> str:
    segments = [
        r"MSH|^~\&|SYNTHETIC|LAB|RECEIVER|LAB|20261018010000||ORU^R01|TEST-F014|P|2.5.1",
        "PID|1||PATIENT-01^^^SYNTHETIC^MR",
        "OBR|1||FILLER-001^LAB|111^Test A^99TEST",
        f"SPM|1|{first_specimen}|",
        "OBX|1|NM|A^Analyte A^99TEST||5|mg/dL|||||F",
        "OBR|2||FILLER-002^LAB|222^Test B^99TEST",
        f"SPM|2|{second_specimen}|",
    ]
    if second_observation:
        segments.append("OBX|1|NM|B^Analyte B^99TEST||9|mg/dL|||||F")
    return "\r".join(segments) + "\r"


def _segment_lines(message: str, segment: str) -> list[str]:
    return [
        line
        for line in message.split("\r")
        if line.startswith(segment + "|")
    ]


def test_f014_swaps_only_two_distinct_group_specimen_identifiers() -> None:
    original = _message()
    fault = swap_specimen_identifiers(original)
    assert fault.fault_id == "F014"
    assert fault.expected_classification == "MISATTRIBUTION"
    assert fault.expected_severity == "S3"
    assert fault.structural_validity_expected is True
    assert fault.target_path == "SPM[0]-2<->SPM[1]-2"
    old_lines = original.split("\r")
    new_lines = fault.artifact.split("\r")
    assert len(old_lines) == len(new_lines)
    assert _segment_lines(original, "OBR") == _segment_lines(fault.artifact, "OBR")
    assert _segment_lines(original, "OBX") == _segment_lines(fault.artifact, "OBX")
    assert [line.split("|")[2] for line in _segment_lines(fault.artifact, "SPM")] == [
        "SPEC-B^LAB", "SPEC-A^LAB"
    ]
    assert sum(a != b for a, b in zip(old_lines, new_lines, strict=True)) == 2


def test_f014_rejects_identical_specimens_without_mutation() -> None:
    with pytest.raises(ValueError, match="no-op"):
        swap_specimen_identifiers(_message(second_specimen="SPEC-A^LAB"))


def test_f014_rejects_specimens_within_one_report_group() -> None:
    lines = [
        r"MSH|^~\&|SYNTHETIC|LAB|RECEIVER|LAB|20261018010000||ORU^R01|TEST|P|2.5.1",
        "OBR|1||FILLER-001|111^Test A^99TEST",
        "SPM|1|SPEC-A^LAB",
        "SPM|2|SPEC-B^LAB",
        "OBX|1|NM|A^Analyte A^99TEST||5|mg/dL|||||F",
    ]
    with pytest.raises(ValueError, match="two distinct OBR"):
        swap_specimen_identifiers("\r".join(lines) + "\r")


def test_f014_rejects_missing_result_in_one_selected_group() -> None:
    with pytest.raises(ValueError, match="OBX result"):
        swap_specimen_identifiers(_message(second_observation=False))


def test_f014_rejects_extra_specimen_ambiguity_in_selected_group() -> None:
    lines = _message().split("\r")
    first_spm_index = next(i for i, line in enumerate(lines) if line.startswith("SPM|"))
    lines.insert(first_spm_index + 1, "SPM|2|SPEC-C^LAB")
    with pytest.raises(ValueError, match="unique SPM"):
        swap_specimen_identifiers("\r".join(lines))


def test_f014_rejects_pre_obr_specimen_with_no_order_context() -> None:
    lines = _message().split("\r")
    lines.insert(1, "SPM|1|SPEC-OUTSIDE^LAB")
    with pytest.raises(ValueError, match="one OBR group"):
        swap_specimen_identifiers("\r".join(lines), first_occurrence=0, second_occurrence=2)


@pytest.mark.parametrize("first,second", [(0, 0), (-1, 1), (0, 4)])
def test_f014_rejects_missing_or_same_specimen_occurrence(
    first: int, second: int
) -> None:
    with pytest.raises(ValueError):
        swap_specimen_identifiers(
            _message(), first_occurrence=first, second_occurrence=second
        )


def test_f014_never_claims_normative_edition5_validity_from_group_shape() -> None:
    result = swap_specimen_identifiers(_message())
    assert result.fault_id == "F014"
    assert result.artifact != _message()
    # The structural_validity_expected metadata is a synthetic stimulus
    # expectation. No independent G1 certificate or qualified validator
    # observation is added by this operator.
    assert not hasattr(result, "G1_qualified")
    assert not hasattr(result, "confirmatory_permission")
