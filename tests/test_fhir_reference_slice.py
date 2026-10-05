from pathlib import Path

from fhirbridge.canonical import generate_lab_scenario
from fhirbridge.lifters import FhirR4LabLifter
from fhirbridge.renderers import FhirR4LabRendererA
from fhirbridge.schema_validation import load_yaml
from fhirbridge.verifier import classify_graph


_CONTRACT_PATH = Path("contracts/fhir_to_v2/lab_oru_r01_v0.2.yaml")


def _round_trip(template_id: str, seed: int):
    graph = generate_lab_scenario(template_id, seed)
    contract = load_yaml(_CONTRACT_PATH)
    rendered = FhirR4LabRendererA().render(graph, contract=contract)
    lifted = FhirR4LabLifter().lift(
        rendered.artifact,
        artifact_id=f"{template_id}-{seed}-fhir-a",
    )
    result = classify_graph(graph["facts"], list(lifted.facts))
    return graph, rendered, lifted, result


def _resource_ids(rendered) -> set[str]:
    return {
        entry["resource"]["id"]
        for entry in rendered.artifact.get("entry", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("resource"), dict)
        and entry["resource"].get("id") is not None
    }


def test_renderer_uses_representation_local_ids() -> None:
    graph, rendered, _, _ = _round_trip("LAB-001", 9001)

    canonical_ids = {fact["fact_id"] for fact in graph["facts"]}
    assert _resource_ids(rendered).isdisjoint(canonical_ids)


def test_basic_numeric_lab_round_trip_is_semantically_faithful() -> None:
    _, rendered, lifted, result = _round_trip("LAB-001", 9002)

    assert rendered.artifact["resourceType"] == "Bundle"
    assert rendered.manifest.metadata["structural_validation_status"] == "not_run_by_renderer"
    assert not lifted.warnings
    assert result.faithful
    assert {decision.classification for decision in result.decisions} == {
        "VERIFIED_EQUIVALENT"
    }


def test_specimen_linked_lab_round_trip_is_semantically_faithful() -> None:
    _, _, lifted, result = _round_trip("LAB-006", 9003)

    specimen = next(fact for fact in lifted.facts if fact.fact_type == "specimen")
    observation = next(fact for fact in lifted.facts if fact.fact_type == "observation")
    assert any(
        relation_type == "specimen_for_observation"
        and target_id == observation.lifted_fact_id
        for relation_type, target_id in specimen.relationships
    )
    assert any(
        relation_type == "specimen" and target_id == specimen.lifted_fact_id
        for relation_type, target_id in observation.relationships
    )
    assert result.faithful


def test_coded_qualitative_value_round_trip_preserves_text_and_code() -> None:
    graph, rendered, lifted, result = _round_trip("LAB-004", 9004)

    source_observation = next(
        fact for fact in graph["facts"] if fact["fact_type"] == "observation"
    )
    rendered_observation = next(
        entry["resource"]
        for entry in rendered.artifact["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    )
    lifted_observation = next(
        fact for fact in lifted.facts if fact.fact_type == "observation"
    )

    assert rendered_observation["valueCodeableConcept"]["text"] == source_observation["value"]
    assert lifted_observation.semantic_payload["value"] == source_observation["value"]
    assert (
        lifted_observation.semantic_payload["attributes"]["value_code"]["code"]
        == source_observation["attributes"]["value_code"]["code"]
    )
    assert result.faithful


def test_repeated_same_code_observations_are_disambiguated_by_time() -> None:
    graph, _, lifted, result = _round_trip("LAB-011", 9005)

    source_observations = [
        fact for fact in graph["facts"] if fact["fact_type"] == "observation"
    ]
    lifted_observations = [
        fact for fact in lifted.facts if fact.fact_type == "observation"
    ]
    assert len(source_observations) == len(lifted_observations) == 2
    assert result.faithful
    assert all(
        result.grounding[fact["fact_id"]].status == "grounded"
        for fact in source_observations
    )


def test_renderer_does_not_encode_report_membership_through_derived_from() -> None:
    _, rendered, lifted, _ = _round_trip("LAB-001", 9006)

    observation_resource = next(
        entry["resource"]
        for entry in rendered.artifact["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    )
    lifted_observation = next(
        fact for fact in lifted.facts if fact.fact_type == "observation"
    )

    assert "derivedFrom" not in observation_resource
    assert any(
        relation_type == "belongs_to_report"
        for relation_type, _ in lifted_observation.relationships
    )


def test_fhir_reference_slice_has_no_indeterminate_decisions() -> None:
    for index, template_id in enumerate(("LAB-001", "LAB-004", "LAB-006", "LAB-011")):
        _, _, _, result = _round_trip(template_id, 9100 + index)
        assert all(
            decision.classification != "INDETERMINATE"
            for decision in result.decisions
        )
