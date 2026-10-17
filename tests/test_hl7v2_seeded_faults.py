"""Qualification checks that seeded semantic faults survive real v2 serialization.

These tests compare the untouched canonical source against a target artifact
rendered from a separately mutated graph, then independently lifted from ER7.
They therefore exercise the full measurement path instead of handing canonical
mutants directly to the verifier.
"""

import fhirbridge.canonical
import fhirbridge.faults
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _classify_serialized_fault(source: dict, target_graph: dict):
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        target_graph,
        contract=contract,
    )
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        rendered.artifact,
        artifact_id=f"{source['graph_id']}-seeded-v2",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    return fhirbridge.verifier.classify_graph(
        source["facts"],
        list(lifted.facts),
        policy=policy,
    )


def _decisions(result, classification: str):
    return [
        decision
        for decision in result.decisions
        if decision.classification == classification
    ]


def test_serialized_numeric_value_fault_is_detected() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9401)
    mutant = fhirbridge.faults.corrupt_numeric_value(source, delta=17)

    result = _classify_serialized_fault(source, mutant.graph)

    assert not result.faithful
    assert any(
        decision.error_subtype == "value"
        for decision in _decisions(result, "CORRUPTION")
    )


def test_serialized_unit_fault_is_detected() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9402)
    mutant = fhirbridge.faults.corrupt_unit_without_conversion(
        source,
        replacement_unit="g/L",
    )

    result = _classify_serialized_fault(source, mutant.graph)

    assert not result.faithful
    assert any(
        decision.error_subtype == "unit"
        for decision in _decisions(result, "CORRUPTION")
    )


def test_serialized_terminology_fault_is_detected() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9403)
    mutant = fhirbridge.faults.corrupt_observation_code(
        source,
        replacement_code="9999-9",
        replacement_display="Non-equivalent synthetic analyte",
    )

    result = _classify_serialized_fault(source, mutant.graph)

    assert not result.faithful
    assert any(
        decision.error_subtype == "terminology"
        for decision in _decisions(result, "CORRUPTION")
    )


def test_serialized_required_observation_omission_is_detected() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-005", 9404)
    mutant = fhirbridge.faults.omit_required_observation(source)

    result = _classify_serialized_fault(source, mutant.graph)

    assert not result.faithful
    assert _decisions(result, "OMISSION")
    assert not _decisions(result, "FABRICATION")


def test_serialized_unsupported_observation_is_fabrication() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9405)
    mutant = fhirbridge.faults.fabricate_observation(source)

    result = _classify_serialized_fault(source, mutant.graph)

    assert not result.faithful
    assert _decisions(result, "FABRICATION")
    assert not _decisions(result, "OMISSION")


def test_serialized_temporal_fault_is_detected() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 9406)
    mutant = fhirbridge.faults.shift_observation_time(source, minutes=90)

    result = _classify_serialized_fault(source, mutant.graph)

    assert not result.faithful
    assert any(
        decision.error_subtype == "temporal"
        for decision in _decisions(result, "CORRUPTION")
    )
