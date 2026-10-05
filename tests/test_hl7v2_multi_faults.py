import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.multi_faults
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _classify(source: dict, mutated_target: dict):
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    artifact = fhirbridge.renderers.Hl7V251OruRendererA().render(
        mutated_target,
        contract=contract,
    ).artifact
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        artifact,
        artifact_id=f"{source['graph_id']}-multi-fault",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    return fhirbridge.verifier.classify_graph(
        source["facts"],
        list(lifted.facts),
        policy=policy,
    )


def _classes(result) -> set[str]:
    return {decision.classification for decision in result.decisions}


def test_mf001_joint_value_unit_corruption_survives_render_lift_and_scores_corruption() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-001", 8201)
    mutant = fhirbridge.multi_faults.value_plus_unit_joint_corruption(
        source,
        value_delta=9,
        replacement_unit="mmol/L",
    )

    result = _classify(source, mutant.graph)

    assert mutant.fault.fault_id == "MF001"
    assert not result.faithful
    assert "CORRUPTION" in _classes(result)


def test_mf003_omission_and_fabrication_are_both_retained_after_serialization() -> None:
    source = fhirbridge.canonical.generate_lab_scenario("LAB-005", 8202)
    mutant = fhirbridge.multi_faults.omission_plus_fabricated_replacement(source)

    result = _classify(source, mutant.graph)
    classes = _classes(result)

    assert mutant.fault.fault_id == "MF003"
    assert not result.faithful
    assert "OMISSION" in classes
    assert "FABRICATION" in classes
