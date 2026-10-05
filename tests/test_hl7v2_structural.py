import fhirbridge.canonical
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.structural

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _artifact(template_id: str = "LAB-001", seed: int = 9501) -> str:
    graph = fhirbridge.canonical.generate_lab_scenario(template_id, seed)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    return fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    ).artifact


def _validator() -> fhirbridge.structural.Hl7V251OruDevelopmentValidator:
    return fhirbridge.structural.Hl7V251OruDevelopmentValidator()


def _without_field(artifact: str, segment_name: str, field_number: int) -> str:
    output: list[str] = []
    for line in artifact.split("\r"):
        if not line:
            continue
        fields = line.split("|")
        if fields[0] == segment_name and field_number < len(fields):
            fields[field_number] = ""
        output.append("|".join(fields))
    return "\r".join(output) + "\r"


def _replace_field(
    artifact: str,
    segment_name: str,
    field_number: int,
    value: str,
) -> str:
    output: list[str] = []
    for line in artifact.split("\r"):
        if not line:
            continue
        fields = line.split("|")
        if fields[0] == segment_name and field_number < len(fields):
            fields[field_number] = value
        output.append("|".join(fields))
    return "\r".join(output) + "\r"


def _codes(result) -> set[str]:
    return {finding.code for finding in result.findings}


def test_clean_reference_artifact_passes_development_structural_gate() -> None:
    result = _validator().validate(_artifact())

    assert result.valid
    assert not any(finding.severity == "error" for finding in result.findings)
    assert result.metadata is not None
    assert result.metadata["profile_level_conformance_claimed"] is False


def test_wrong_message_type_is_structurally_invalid() -> None:
    artifact = _replace_field(_artifact(), "MSH", 8, "ADT^A01^ADT_A01")

    result = _validator().validate(artifact)

    assert not result.valid
    assert "WRONG_MESSAGE_TYPE" in _codes(result)


def test_wrong_version_is_structurally_invalid() -> None:
    artifact = _replace_field(_artifact(), "MSH", 11, "2.3")

    result = _validator().validate(artifact)

    assert not result.valid
    assert "WRONG_VERSION" in _codes(result)


def test_missing_pid3_is_structurally_invalid() -> None:
    artifact = _without_field(_artifact(), "PID", 3)

    result = _validator().validate(artifact)

    assert not result.valid
    assert "PID3_REQUIRED" in _codes(result)


def test_missing_obx_value_is_structurally_invalid() -> None:
    artifact = _without_field(_artifact(), "OBX", 5)

    result = _validator().validate(artifact)

    assert not result.valid
    assert "OBX5_REQUIRED" in _codes(result)


def test_missing_obx_status_is_structurally_invalid() -> None:
    artifact = _without_field(_artifact(), "OBX", 11)

    result = _validator().validate(artifact)

    assert not result.valid
    assert "OBX11_REQUIRED" in _codes(result)


def test_invalid_timestamp_shape_is_structurally_invalid() -> None:
    artifact = _replace_field(_artifact(), "OBX", 14, "not-a-timestamp")

    result = _validator().validate(artifact)

    assert not result.valid
    assert "INVALID_TS_SHAPE" in _codes(result)


def test_f018_syntax_only_fault_is_a_structural_negative_control() -> None:
    clean = _artifact()
    malformed = _replace_field(clean, "MSH", 11, "INVALID")

    clean_result = _validator().validate(clean)
    malformed_result = _validator().validate(malformed)

    assert clean_result.valid
    assert not malformed_result.valid
    assert "WRONG_VERSION" in _codes(malformed_result)
