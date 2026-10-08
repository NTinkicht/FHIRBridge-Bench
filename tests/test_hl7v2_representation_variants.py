import pytest

import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.structural
import fhirbridge.verifier

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _render(template_id: str = "LAB-001", seed: int = 9601):
    graph = fhirbridge.canonical.generate_lab_scenario(template_id, seed)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )
    return graph, contract, rendered.artifact


def _lift_and_classify(graph: dict, contract: dict, artifact: str):
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id="representation-variant",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    result = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=policy,
    )
    return lifted, result


def _replace_first_field(
    artifact: str,
    segment_name: str,
    field_number: int,
    transform,
) -> str:
    output: list[str] = []
    replaced = False
    for line in artifact.split("\r"):
        if not line:
            continue
        fields = line.split("|")
        if not replaced and fields[0] == segment_name and field_number < len(fields):
            fields[field_number] = transform(fields[field_number])
            replaced = True
        output.append("|".join(fields))
    assert replaced
    return "\r".join(output) + "\r"


def _replace_first_component(
    artifact: str,
    segment_name: str,
    field_number: int,
    component_number: int,
    replacement: str,
) -> str:
    def transform(value: str) -> str:
        components = value.split("^")
        while len(components) < component_number:
            components.append("")
        components[component_number - 1] = replacement
        return "^".join(components)

    return _replace_first_field(
        artifact,
        segment_name,
        field_number,
        transform,
    )


def _duplicate_first_segment(artifact: str, segment_name: str) -> str:
    output: list[str] = []
    duplicated = False
    for line in artifact.split("\r"):
        if not line:
            continue
        output.append(line)
        if not duplicated and line.startswith(f"{segment_name}|"):
            output.append(line)
            duplicated = True
    assert duplicated
    return "\r".join(output) + "\r"


def _insert_after_first_segment(
    artifact: str,
    segment_name: str,
    new_segment: str,
) -> str:
    output: list[str] = []
    inserted = False
    for line in artifact.split("\r"):
        if not line:
            continue
        output.append(line)
        if not inserted and line.startswith(f"{segment_name}|"):
            output.append(new_segment)
            inserted = True
    assert inserted
    return "\r".join(output) + "\r"


def _structural_codes(result) -> set[str]:
    return {finding.code for finding in result.findings}


def test_numeric_lexical_variant_is_structurally_valid_and_semantically_equivalent() -> None:
    graph, contract, artifact = _render("LAB-001", 9601)

    def equivalent_numeric_lexeme(value: str) -> str:
        assert value
        return f"{value}.0" if "." not in value else f"{value}0"

    variant = _replace_first_field(
        artifact,
        "OBX",
        5,
        equivalent_numeric_lexeme,
    )

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(variant)
    lifted, result = _lift_and_classify(graph, contract, variant)

    assert structural.valid
    observation = next(fact for fact in lifted.facts if fact.fact_type == "observation")
    source_observation = next(
        fact for fact in graph["facts"] if fact["fact_type"] == "observation"
    )
    assert observation.semantic_payload["value"] == source_observation["value"]
    assert result.faithful
    assert all(
        decision.classification == "VERIFIED_EQUIVALENT"
        for decision in result.decisions
    )


def test_code_display_variant_does_not_change_coded_concept_identity() -> None:
    graph, contract, artifact = _render("LAB-001", 9602)
    variant = _replace_first_component(
        artifact,
        "OBX",
        3,
        2,
        "Alternate human-readable display",
    )

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(variant)
    lifted, result = _lift_and_classify(graph, contract, variant)

    assert structural.valid
    target_observation = next(
        fact for fact in lifted.facts if fact.fact_type == "observation"
    )
    source_observation = next(
        fact for fact in graph["facts"] if fact["fact_type"] == "observation"
    )
    assert target_observation.semantic_payload["concept"]["code"] == (
        source_observation["concept"]["code"]
    )
    assert target_observation.semantic_payload["concept"]["system"] == (
        source_observation["concept"]["system"]
    )
    assert target_observation.semantic_payload["concept"]["display"] != (
        source_observation["concept"]["display"]
    )
    assert result.faithful


def test_out_of_slice_segment_is_warning_not_a_silent_semantic_error() -> None:
    graph, contract, artifact = _render("LAB-001", 9603)
    variant = _insert_after_first_segment(
        artifact,
        "OBR",
        "NTE|1||Development-only unmapped note",
    )

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(variant)
    lifted, result = _lift_and_classify(graph, contract, variant)

    assert structural.valid
    assert "OUT_OF_SLICE_SEGMENT" in _structural_codes(structural)
    assert any(warning.code == "UNLIFTED_SEGMENT" for warning in lifted.warnings)
    assert result.faithful
    assert all(
        decision.classification != "FABRICATION"
        for decision in result.decisions
    )


def test_duplicate_pid_remains_outside_scored_development_slice() -> None:
    _, _, artifact = _render("LAB-001", 9604)
    variant = _duplicate_first_segment(artifact, "PID")

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(variant)

    assert not structural.valid
    assert "MULTIPLE_PID" in _structural_codes(structural)
    with pytest.raises(ValueError, match="exactly one PID and at least one OBR"):
        fhirbridge.lifters.Hl7V251OruLifter().lift(
            variant,
            artifact_id="duplicate-pid",
        )


def test_duplicate_obr_is_parseable_but_invalid_when_first_group_has_no_obx() -> None:
    _, _, artifact = _render("LAB-001", 9605)
    variant = _duplicate_first_segment(artifact, "OBR")

    structural = fhirbridge.structural.Hl7V251OruDevelopmentValidator().validate(variant)

    assert not structural.valid
    assert "OBR_GROUP_WITHOUT_OBX" in _structural_codes(structural)

    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        variant,
        artifact_id="duplicate-obr",
    )
    assert lifted.metadata["report_count"] == 2
    assert lifted.metadata["observation_count"] == 1
