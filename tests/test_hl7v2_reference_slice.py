import fhirbridge.canonical
import fhirbridge.lifters
import fhirbridge.renderers
import fhirbridge.schema_validation
import fhirbridge.verifier

_CONTRACT_PATH = "contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml"


def _round_trip(template_id: str, seed: int):
    graph = fhirbridge.canonical.generate_lab_scenario(template_id, seed)
    contract = fhirbridge.schema_validation.load_yaml(_CONTRACT_PATH)
    rendered = fhirbridge.renderers.Hl7V251OruRendererA().render(
        graph,
        contract=contract,
    )
    lifted = fhirbridge.lifters.Hl7V251OruLifter().lift(
        rendered.artifact,
        artifact_id=f"{template_id}-{seed}-v2-a",
    )
    policy = fhirbridge.verifier.compile_verification_policy(contract)
    result = fhirbridge.verifier.classify_graph(
        graph["facts"],
        list(lifted.facts),
        policy=policy,
    )
    return graph, rendered, lifted, result


def test_numeric_lab_round_trip_is_semantically_faithful() -> None:
    _, rendered, lifted, result = _round_trip("LAB-001", 9201)

    assert isinstance(rendered.artifact, str)
    assert rendered.artifact.startswith("MSH|^~\\&|")
    assert "\rPID|" in rendered.artifact
    assert "\rOBR|" in rendered.artifact
    assert "\rOBX|" in rendered.artifact
    assert lifted.metadata["message_type"].startswith("ORU^R01")
    assert lifted.metadata["version"] == "2.5.1"
    assert result.faithful
    assert {decision.classification for decision in result.decisions} == {
        "VERIFIED_EQUIVALENT"
    }


def test_coded_qualitative_value_survives_v2_lifting() -> None:
    graph, _, lifted, result = _round_trip("LAB-004", 9202)

    source = next(
        fact for fact in graph["facts"] if fact["fact_type"] == "observation"
    )
    target = next(fact for fact in lifted.facts if fact.fact_type == "observation")
    assert target.semantic_payload["value"] == source["value"]
    assert (
        target.semantic_payload["attributes"]["value_code"]["code"]
        == source["attributes"]["value_code"]["code"]
    )
    assert result.faithful


def test_specimen_relationships_survive_v2_lifting() -> None:
    _, rendered, lifted, result = _round_trip("LAB-006", 9203)

    assert "\rSPM|" in rendered.artifact
    specimen = next(fact for fact in lifted.facts if fact.fact_type == "specimen")
    observation = next(fact for fact in lifted.facts if fact.fact_type == "observation")
    report = next(
        fact for fact in lifted.facts if fact.fact_type == "diagnostic_report"
    )
    assert ("specimen", specimen.lifted_fact_id) in observation.relationships
    assert ("has_specimen", specimen.lifted_fact_id) in report.relationships
    assert (
        "specimen_for_observation",
        observation.lifted_fact_id,
    ) in specimen.relationships
    assert result.faithful


def test_repeated_same_code_observations_are_grounded_by_time() -> None:
    graph, _, lifted, result = _round_trip("LAB-011", 9204)

    source_observations = [
        fact for fact in graph["facts"] if fact["fact_type"] == "observation"
    ]
    target_observations = [
        fact for fact in lifted.facts if fact.fact_type == "observation"
    ]
    assert len(source_observations) == len(target_observations) == 2
    assert result.faithful
    assert all(
        result.grounding[fact["fact_id"]].status == "grounded"
        for fact in source_observations
    )


def test_timezone_normalization_preserves_semantic_time() -> None:
    _, _, _, result = _round_trip("LAB-009", 9205)

    assert result.faithful
    assert all(
        decision.classification != "INDETERMINATE"
        for decision in result.decisions
    )


def test_patient_identifier_repetitions_are_preserved() -> None:
    graph, _, lifted, result = _round_trip("LAB-010", 9206)

    source_patient = next(
        fact for fact in graph["facts"] if fact["fact_type"] == "patient_identity"
    )
    target_patient = next(
        fact for fact in lifted.facts if fact.fact_type == "patient_identity"
    )
    assert len(source_patient["identifiers"]) == 2
    assert target_patient.semantic_payload["identifiers"] == source_patient["identifiers"]
    assert result.faithful


def test_primary_v2_reference_slice_has_no_indeterminate_decisions() -> None:
    templates = ("LAB-001", "LAB-004", "LAB-006", "LAB-009", "LAB-010", "LAB-011")
    for index, template_id in enumerate(templates):
        _, _, _, result = _round_trip(template_id, 9300 + index)
        assert all(
            decision.classification != "INDETERMINATE"
            for decision in result.decisions
        )
