from fhirbridge.syntax_repair import repair_hl7_text_syntax


def test_repair_normalizes_only_wrappers_and_segment_terminators() -> None:
    fence = chr(96) * 3
    raw = (
        fence
        + "hl7\n"
        + "MSH|^~\\&|APP|FAC|||20261010||ORU^R01^ORU_R01|1|P|2.5.1\n"
        + "PID|1||PAT-1^^^MPI^MR||Doe^Jane\n"
        + fence
    )

    result = repair_hl7_text_syntax(raw)

    assert result.output == (
        "MSH|^~\\&|APP|FAC|||20261010||ORU^R01^ORU_R01|1|P|2.5.1\r"
        "PID|1||PAT-1^^^MPI^MR||Doe^Jane\r"
    )
    assert result.changed
    assert "remove_single_outer_markdown_fence" in result.operations
    assert (
        "normalize_segment_terminators_and_outer_blank_lines"
        in result.operations
    )


def test_repair_preserves_every_character_inside_nonempty_segments() -> None:
    first = "OBX|1|ST|CODE^Display^LN||  value with spaces  |"
    second = "NTE|1||A^B|C\\F\\D"
    raw = first + "\n\n" + second + "\n"

    result = repair_hl7_text_syntax(raw)

    assert result.output == first + "\r" + second + "\r"
    assert result.output.split("\r")[0] == first
    assert result.output.split("\r")[1] == second


def test_repair_does_not_invent_missing_required_segments_or_fields() -> None:
    raw = "OBX|1|NM|||42\n"

    result = repair_hl7_text_syntax(raw)

    assert result.output == "OBX|1|NM|||42\r"
    assert "MSH|" not in result.output
    assert "PID|" not in result.output
    assert "OBR|" not in result.output


def test_repair_does_not_strip_unrecognized_markdown_fence_language() -> None:
    fence = chr(96) * 3
    raw = fence + "json\nMSH|^~\\&|APP\n" + fence

    result = repair_hl7_text_syntax(raw)

    assert result.output.startswith(fence + "json\r")
    assert "remove_single_outer_markdown_fence" not in result.operations


def test_repair_removes_bom_without_changing_segment_payload() -> None:
    segment = "MSH|^~\\&|APP|FAC"
    result = repair_hl7_text_syntax("\ufeff" + segment + "\r")

    assert result.output == segment + "\r"
    assert "remove_utf8_bom" in result.operations


def test_repair_is_idempotent_for_canonical_hl7_text() -> None:
    raw = "MSH|^~\\&|APP|FAC\rPID|1||P1\r"

    first = repair_hl7_text_syntax(raw)
    second = repair_hl7_text_syntax(first.output)

    assert first.output == raw
    assert not first.changed
    assert second.output == raw
    assert not second.changed
    assert first.output_sha256 == second.output_sha256
