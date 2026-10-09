from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.hl7v2_negative_controls import build_structural_negative_controls
from fhirbridge.renderers import Hl7V251OruRendererA
from fhirbridge.schema_validation import load_yaml

_CONTRACT = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _message() -> str:
    graph = generate_lab_scenario("LAB-001", 9801)
    contract = load_yaml(_CONTRACT)
    return Hl7V251OruRendererA().render(graph, contract=contract).artifact


def _msh_fields(message: str) -> list[str]:
    msh = message.replace("\n", "\r").split("\r")[0]
    return msh.split("|")


def test_negative_controls_are_stable_and_high_confidence() -> None:
    controls = build_structural_negative_controls(_message())

    assert [item.control_id for item in controls] == [
        "NEG-HL7-VERSION",
        "NEG-MESSAGE-STRUCTURE",
        "NEG-MISSING-PID",
    ]
    assert all(item.expected_structural_error for item in controls)


def test_version_negative_changes_only_msh_12_identity() -> None:
    source = _message()
    control = build_structural_negative_controls(source)[0]

    source_fields = _msh_fields(source)
    target_fields = _msh_fields(control.artifact)

    assert source_fields[11] == "2.5.1"
    assert target_fields[11] == "2.3.1"
    assert source_fields[:11] == target_fields[:11]


def test_message_structure_negative_changes_msh_9() -> None:
    control = build_structural_negative_controls(_message())[1]

    assert _msh_fields(control.artifact)[8] == "ADT^A01^ADT_A01"


def test_missing_pid_negative_preserves_other_core_segments() -> None:
    control = build_structural_negative_controls(_message())[2]
    segment_names = [
        segment.split("|", 1)[0]
        for segment in control.artifact.split("\r")
        if segment
    ]

    assert "PID" not in segment_names
    assert segment_names[0] == "MSH"
    assert "OBR" in segment_names
    assert "OBX" in segment_names
